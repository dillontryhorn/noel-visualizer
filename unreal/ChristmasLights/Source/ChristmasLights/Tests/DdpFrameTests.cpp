#include "DdpFrame.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include <initializer_list>

namespace
{
TArray<uint8> Packet(uint32 Offset, std::initializer_list<uint8> Values, bool Push, uint8 Type = 0x0B)
{
    const uint16 Length = uint16(Values.size());
    TArray<uint8> Bytes{uint8(Push ? 0x41 : 0x40), 1, Type, 1,
        uint8(Offset >> 24), uint8(Offset >> 16), uint8(Offset >> 8), uint8(Offset), uint8(Length >> 8), uint8(Length)};
    for (const uint8 Value : Values) Bytes.Add(Value);
    return Bytes;
}
EDdpResult Apply(FDdpFrame& Frame, const TArray<uint8>& Bytes)
{
    FString Error;
    return Frame.Accept(Bytes.GetData(), Bytes.Num(), Error);
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDdpAssemblyTest, "ChristmasLights.DDP.ChunkAssembly",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FDdpAssemblyTest::RunTest(const FString& Parameters)
{
    FDdpFrame Frame(6);
    TestTrue(TEXT("First chunk stays buffered"), Apply(Frame, Packet(0, {255, 0, 0}, false)) == EDdpResult::Buffered);
    TestTrue(TEXT("No visible change until PUSH"), Frame.GetChannels() == TArray<uint8>({0, 0, 0, 0, 0, 0}));
    TestTrue(TEXT("PUSH commits all chunks"), Apply(Frame, Packet(3, {0, 255, 0}, true)) == EDdpResult::Committed);
    TestTrue(TEXT("Two correct RGB pixels"), Frame.GetChannels() == TArray<uint8>({255, 0, 0, 0, 255, 0}));
    TestTrue(TEXT("Partial write commits"), Apply(Frame, Packet(1, {20}, true)) == EDdpResult::Committed);
    TestTrue(TEXT("Untouched channels persist"), Frame.GetChannels() == TArray<uint8>({255, 20, 0, 0, 255, 0}));
    TestFalse(TEXT("No pending transaction after PUSH"), Frame.HasPending());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDdpValidationTest, "ChristmasLights.DDP.Validation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FDdpValidationTest::RunTest(const FString& Parameters)
{
    FDdpFrame Frame(6);
    TestTrue(TEXT("Truncated header rejected"), Apply(Frame, TArray<uint8>({0x41, 1})) == EDdpResult::Rejected);
    TestTrue(TEXT("Oversized offset rejected"), Apply(Frame, Packet(0xFFFFFFFF, {1}, true)) == EDdpResult::Rejected);
    TestTrue(TEXT("Channel overflow rejected"), Apply(Frame, Packet(5, {1, 2}, true)) == EDdpResult::Rejected);
    TArray<uint8> BadLength = Packet(0, {1, 2, 3}, true);
    BadLength[9] = 4;
    TestTrue(TEXT("Length mismatch rejected"), Apply(Frame, BadLength) == EDdpResult::Rejected);
    TArray<uint8> Timestamp = Packet(0, {1, 2, 3}, true);
    Timestamp[0] |= 0x10;
    TestTrue(TEXT("Unsupported timestamp rejected"), Apply(Frame, Timestamp) == EDdpResult::Rejected);
    TestTrue(TEXT("RGBW rejected"), Apply(Frame, Packet(0, {1, 2, 3, 4}, true, 0x1B)) == EDdpResult::Rejected);
    TArray<uint8> WrongId = Packet(0, {1, 2, 3}, true);
    WrongId[3] = 250;
    TestTrue(TEXT("Configuration destination rejected"), Apply(Frame, WrongId) == EDdpResult::Rejected);
    TestTrue(TEXT("Rejected packets leave visible channels untouched"), Frame.GetChannels() == TArray<uint8>({0, 0, 0, 0, 0, 0}));
    TestTrue(TEXT("Legacy RGB supported"), Apply(Frame, Packet(0, {1, 2, 3}, true, 1)) == EDdpResult::Committed);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDdpDiscardTest, "ChristmasLights.DDP.DiscardPending",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FDdpDiscardTest::RunTest(const FString& Parameters)
{
    FDdpFrame Frame(6);
    Apply(Frame, Packet(0, {255, 0, 0}, false));
    Frame.DiscardPending();
    Apply(Frame, Packet(3, {0, 0, 255}, true));
    TestTrue(TEXT("Timed-out partial transaction discarded"), Frame.GetChannels() == TArray<uint8>({0, 0, 0, 0, 0, 255}));
    Apply(Frame, Packet(0, {1, 2, 3}, false));
    Frame.Reset(3);
    TestFalse(TEXT("Reset discards pending transaction"), Frame.HasPending());
    TestEqual(TEXT("Reset changes channel count"), Frame.GetChannels().Num(), 3);
    return true;
}
#endif

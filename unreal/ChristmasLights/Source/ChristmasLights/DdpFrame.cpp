#include "DdpFrame.h"

FDdpFrame::FDdpFrame(int32 ChannelCount) { Reset(ChannelCount); }

void FDdpFrame::Reset(int32 ChannelCount)
{
    Channels.Init(0, FMath::Max(0, ChannelCount));
    Pending.Reset();
    bPending = false;
}

void FDdpFrame::DiscardPending()
{
    Pending.Reset();
    bPending = false;
}

EDdpResult FDdpFrame::Accept(const uint8* Data, int32 Size, FString& Error)
{
    Error.Reset();
    auto Reject = [&Error](const TCHAR* Reason) {
        Error = Reason;
        return EDdpResult::Rejected;
    };
    if (!Data || Size < 10) return Reject(TEXT("DDP header truncated"));
    // Version 1, only PUSH supported. TIME requires a longer header.
    if ((Data[0] & 0xFE) != 0x40) return Reject(TEXT("Unsupported DDP version or flags"));
    if ((Data[1] & 0xF0) != 0) return Reject(TEXT("DDP reserved sequence bits set"));
    if ((Data[2] != 0x0B && Data[2] != 0x01) || Data[3] != 1)
        return Reject(TEXT("Expected RGB24/legacy RGB and display ID 1"));
    const uint32 Offset = (uint32(Data[4]) << 24) | (uint32(Data[5]) << 16)
        | (uint32(Data[6]) << 8) | uint32(Data[7]);
    const uint32 Length = (uint32(Data[8]) << 8) | uint32(Data[9]);
    if (uint32(Size - 10) != Length) return Reject(TEXT("DDP payload length mismatch"));
    // 64-bit arithmetic prevents malformed offsets wrapping past the bound.
    if (uint64(Offset) + Length > uint64(Channels.Num())) return Reject(TEXT("DDP exceeds layout channel count"));
    if (!bPending)
    {
        Pending = Channels;
        bPending = true;
    }
    if (Length > 0) FMemory::Memcpy(Pending.GetData() + Offset, Data + 10, Length);
    if ((Data[0] & 1) == 0) return EDdpResult::Buffered;
    Swap(Channels, Pending);
    DiscardPending();
    return EDdpResult::Committed;
}

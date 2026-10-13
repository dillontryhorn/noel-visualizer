#include "SceneGeometry.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSceneTransformTest, "ChristmasLights.Scene.Transform",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FSceneTransformTest::RunTest(const FString& Parameters)
{
    FLightShowSceneObject Object;
    Object.Position = FVector(1, 2, 3);
    TestTrue(TEXT("Base-center origin maps meters and Y-up into Unreal centimeters and Z-up"),
        ChristmasScenePointToUnreal(FVector::ZeroVector, Object).Equals(FVector(300, 100, 200), .001));
    Object.Position = FVector::ZeroVector;
    Object.Rotation = FVector(90, 0, 0);
    TestTrue(TEXT("Positive browser X rotation maps correctly"),
        ChristmasScenePointToUnreal(FVector(1, 2, 3), Object).Equals(FVector(200, 100, -300), .001));
    Object.Rotation = FVector(0, 90, 0);
    TestTrue(TEXT("Positive browser Y rotation maps correctly"),
        ChristmasScenePointToUnreal(FVector(1, 2, 3), Object).Equals(FVector(-100, 300, 200), .001));
    Object.Rotation = FVector(0, 0, 90);
    TestTrue(TEXT("Positive browser Z rotation maps correctly"),
        ChristmasScenePointToUnreal(FVector(1, 2, 3), Object).Equals(FVector(300, -200, 100), .001));
    Object.Position = FVector(5, 7, 11);
    Object.Scale = FVector(2, 3, 4);
    Object.Rotation = FVector(90, 90, 90);
    TestTrue(TEXT("Nonuniform scale then Three.js Euler XYZ rotation then translation"),
        ChristmasScenePointToUnreal(FVector(1, 2, 3), Object).Equals(FVector(1300, 1700, 100), .001));
    return true;
}
#endif

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DdpFrame.h"
#include "SceneGeometry.h"
#include "LightShowActor.generated.h"

class FSocket;
class UInstancedStaticMeshComponent;
class UStaticMesh;
class UMaterialInterface;
class FJsonObject;

UCLASS()
class CHRISTMASLIGHTS_API ALightShowActor : public AActor
{
    GENERATED_BODY()

public:
    ALightShowActor();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="DDP") FString BindAddress = TEXT("127.0.0.1");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="DDP", meta=(ClampMin="1", ClampMax="65535")) int32 ListenPort = 4049;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="DDP", meta=(ClampMin="1", ClampMax="2048")) int32 MaxPacketsPerTick = 256;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="DDP", meta=(ClampMin="0.05")) float PendingTimeoutSeconds = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="DDP", meta=(ClampMin="0.1")) float SignalTimeoutSeconds = 2.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Layout") FString LayoutFile = TEXT("Data/default.json");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Layout", meta=(ClampMin="1", ClampMax="1000000")) int32 MaxChannelCount = 1000000;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Appearance", meta=(ClampMin="0.5")) float PixelRadiusCentimeters = 3.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Appearance") bool bBuildScenery = true;

    FString GetStatus() const;
    int32 GetPixelCount() const { return PixelChannels.Num(); }
    int32 GetChannelCount() const { return Frame.GetChannels().Num(); }
    bool IsReceiving() const;

private:
    bool LoadLayout();
    bool LoadScene(const TSharedPtr<FJsonObject>& Document);
    bool OpenSocket();
    void CloseSocket();
    void ApplyFrame();
    void BuildScenery();
    void BuildSceneObject(const FLightShowSceneObject& Object);
    void AddBox(const FVector& Location, const FVector& Size, const FRotator& Rotation = FRotator::ZeroRotator);

    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> Pixels;
    UPROPERTY() TObjectPtr<UStaticMesh> CubeMesh;
    UPROPERTY() TObjectPtr<UMaterialInterface> SceneryMaterial;
    TArray<int32> PixelChannels;
    TArray<FLightShowSceneObject> SceneObjects;
    bool bHasAuthoredScene = false;
    bool bSceneGroundVisible = true;
    FLinearColor SceneGroundColor = FLinearColor::FromSRGBColor(FColor(131, 152, 178));
    FDdpFrame Frame;
    FSocket* Socket = nullptr;
    TArray<uint8> ReceiveBuffer;
    FString LayoutName;
    FString StartupError;
    uint64 ReceivedPackets = 0;
    uint64 RejectedPackets = 0;
    uint64 CommittedFrames = 0;
    double LastPacketTime = 0.0;
    double LastFrameTime = 0.0;
    double PendingStartTime = 0.0;
};

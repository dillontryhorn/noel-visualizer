#include "LightShowActor.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "IPAddress.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "ProceduralMeshComponent.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SocketSubsystem.h"
#include "Sockets.h"
#include "UObject/ConstructorHelpers.h"
#include <initializer_list>

namespace
{
bool ReadTriple(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, FVector& Out, double Minimum, double Maximum)
{
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!Object->TryGetArrayField(Field, Values) || Values->Num() != 3) return false;
    for (int32 Axis = 0; Axis < 3; ++Axis)
    {
        double Value = 0;
        if (!(*Values)[Axis].IsValid() || !(*Values)[Axis]->TryGetNumber(Value)
            || !FMath::IsFinite(Value) || Value < Minimum || Value > Maximum) return false;
        Out[Axis] = Value;
    }
    return true;
}

bool ReadHexColor(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, FLinearColor& Out)
{
    FString Hex;
    if (!Object->TryGetStringField(Field, Hex) || Hex.Len() != 7 || Hex[0] != TCHAR('#')) return false;
    for (int32 Index = 1; Index < 7; ++Index)
    {
        const TCHAR Digit = Hex[Index];
        if (!((Digit >= TCHAR('0') && Digit <= TCHAR('9'))
            || (Digit >= TCHAR('a') && Digit <= TCHAR('f'))
            || (Digit >= TCHAR('A') && Digit <= TCHAR('F')))) return false;
    }
    Out = FLinearColor::FromSRGBColor(FColor::FromHex(Hex));
    return true;
}

struct FSceneMeshBuilder
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FLinearColor> Colors;

    void Triangle(const FVector& A, const FVector& B, const FVector& C, const FLinearColor& Color)
    {
        const int32 First = Vertices.Num();
        Vertices.Add(A); Vertices.Add(B); Vertices.Add(C);
        Triangles.Add(First); Triangles.Add(First + 1); Triangles.Add(First + 2);
        Colors.Add(Color); Colors.Add(Color); Colors.Add(Color);
    }

    void Quad(const FVector& A, const FVector& B, const FVector& C, const FVector& D, const FLinearColor& Color)
    {
        Triangle(A, B, C, Color); Triangle(A, C, D, Color);
    }

    void Box(const FVector& Center, const FVector& Size, const FLinearColor& Color)
    {
        FVector V[8];
        for (int32 Index = 0; Index < 8; ++Index)
            V[Index] = Center + FVector((Index & 1) ? Size.X / 2 : -Size.X / 2,
                (Index & 2) ? Size.Y / 2 : -Size.Y / 2, (Index & 4) ? Size.Z / 2 : -Size.Z / 2);
        Quad(V[0], V[1], V[3], V[2], Color); Quad(V[4], V[6], V[7], V[5], Color);
        Quad(V[0], V[4], V[5], V[1], Color); Quad(V[2], V[3], V[7], V[6], Color);
        Quad(V[0], V[2], V[6], V[4], Color); Quad(V[1], V[5], V[7], V[3], Color);
    }

    void Cone(double Bottom, double Height, double Radius, const FLinearColor& Color)
    {
        const FVector Tip(0, Bottom + Height, 0), Center(0, Bottom, 0);
        for (int32 Index = 0; Index < 12; ++Index)
        {
            const double A = Index * 2 * PI / 12, B = (Index + 1) * 2 * PI / 12;
            const FVector P(FMath::Cos(A) * Radius, Bottom, FMath::Sin(A) * Radius);
            const FVector Q(FMath::Cos(B) * Radius, Bottom, FMath::Sin(B) * Radius);
            Triangle(P, Q, Tip, Color); Triangle(Center, Q, P, Color);
        }
    }

    void Arch(double CenterX, double Width, double Height, const FLinearColor& Color)
    {
        // Small rectangular tube sections approximate the browser's round tube.
        for (int32 Index = 0; Index < 40; ++Index)
        {
            const double A = Index * PI / 40, B = (Index + 1) * PI / 40;
            const FVector P(CenterX + FMath::Cos(A) * Width / 2, FMath::Sin(A) * Height, 0);
            const FVector Q(CenterX + FMath::Cos(B) * Width / 2, FMath::Sin(B) * Height, 0);
            const FVector N = FVector(-(Q.Y - P.Y), Q.X - P.X, 0).GetSafeNormal() * .022;
            const FVector D(0, 0, .022);
            Quad(P + N + D, Q + N + D, Q - N + D, P - N + D, Color);
            Quad(P - N - D, Q - N - D, Q + N - D, P + N - D, Color);
            Quad(P + N - D, Q + N - D, Q + N + D, P + N + D, Color);
            Quad(P - N + D, Q - N + D, Q - N - D, P - N - D, Color);
        }
    }
};
}

ALightShowActor::ALightShowActor()
{
    PrimaryActorTick.bCanEverTick = true;
    Pixels = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Pixels"));
    SetRootComponent(Pixels);
    Pixels->SetMobility(EComponentMobility::Movable);
    Pixels->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Pixels->SetCastShadow(false);
    Pixels->NumCustomDataFloats = 3;
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (Sphere.Succeeded()) Pixels->SetStaticMesh(Sphere.Object);
    if (Cube.Succeeded()) CubeMesh = Cube.Object;
}

void ALightShowActor::BeginPlay()
{
    Super::BeginPlay();
    // Map-specific overrides take priority over INI defaults; CLI overrides both.
    const ALightShowActor* Defaults = GetClass()->GetDefaultObject<ALightShowActor>();
    if (BindAddress == Defaults->BindAddress) GConfig->GetString(TEXT("ChristmasLights"), TEXT("BindAddress"), BindAddress, GGameIni);
    if (ListenPort == Defaults->ListenPort) GConfig->GetInt(TEXT("ChristmasLights"), TEXT("ListenPort"), ListenPort, GGameIni);
    if (LayoutFile == Defaults->LayoutFile) GConfig->GetString(TEXT("ChristmasLights"), TEXT("LayoutFile"), LayoutFile, GGameIni);
    FParse::Value(FCommandLine::Get(), TEXT("DdpBind="), BindAddress);
    FParse::Value(FCommandLine::Get(), TEXT("DdpPort="), ListenPort);
    FParse::Value(FCommandLine::Get(), TEXT("LightLayout="), LayoutFile);
    MaxChannelCount = FMath::Clamp(MaxChannelCount, 1, 1000000);
    MaxPacketsPerTick = FMath::Clamp(MaxPacketsPerTick, 1, 2048);
    PixelRadiusCentimeters = FMath::Max(PixelRadiusCentimeters, 0.5f);
    PendingTimeoutSeconds = FMath::Max(PendingTimeoutSeconds, 0.05f);
    SignalTimeoutSeconds = FMath::Max(SignalTimeoutSeconds, 0.1f);

    UMaterialInterface* PixelMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Pixel.M_Pixel"));
    SceneryMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Scenery.M_Scenery"));
    if (!PixelMaterial)
    {
        StartupError = TEXT("Missing M_Pixel: run Scripts/setup_assets.py in Unreal Editor first.");
        UE_LOG(LogTemp, Error, TEXT("%s"), *StartupError);
        return;
    }
    Pixels->SetMaterial(0, PixelMaterial);
    if (!LoadLayout())
    {
        UE_LOG(LogTemp, Error, TEXT("%s"), *StartupError);
        return;
    }
    if (bBuildScenery) BuildScenery();
    ApplyFrame();
    if (!OpenSocket()) UE_LOG(LogTemp, Error, TEXT("%s"), *StartupError);
}

bool ALightShowActor::LoadLayout()
{
    const FString Path = FPaths::IsRelative(LayoutFile)
        ? FPaths::Combine(FPaths::ProjectContentDir(), LayoutFile) : LayoutFile;
    FString Json;
    TSharedPtr<FJsonObject> Document;
    if (!FFileHelper::LoadFileToString(Json, *Path)
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Document)
        || !Document.IsValid())
    {
        StartupError = FString::Printf(TEXT("Cannot read layout JSON: %s"), *Path);
        return false;
    }
    const TArray<TSharedPtr<FJsonValue>>* Fixtures = nullptr;
    if (!Document->TryGetStringField(TEXT("name"), LayoutName)
        || !Document->TryGetArrayField(TEXT("fixtures"), Fixtures) || Fixtures->IsEmpty())
    {
        StartupError = TEXT("Layout requires name and a nonempty fixtures array.");
        return false;
    }
    TArray<FVector> Positions;
    TArray<int32> Channels;
    TBitArray<> Occupied(false, MaxChannelCount);
    TSet<FString> Ids;
    int32 ChannelCount = 0;
    for (const TSharedPtr<FJsonValue>& FixtureValue : *Fixtures)
    {
        if (!FixtureValue.IsValid() || FixtureValue->Type != EJson::Object)
        {
            StartupError = TEXT("Every fixture must be an object.");
            return false;
        }
        const TSharedPtr<FJsonObject> Fixture = FixtureValue->AsObject();
        const TArray<TSharedPtr<FJsonValue>>* Points = nullptr;
        double Start = 0;
        FString Id;
        if (!Fixture->TryGetStringField(TEXT("id"), Id) || Id.IsEmpty() || Ids.Contains(Id)
            || !Fixture->TryGetNumberField(TEXT("startChannel"), Start)
            || !FMath::IsFinite(Start) || Start < 1 || Start > MaxChannelCount || Start != double(int32(Start))
            || !Fixture->TryGetArrayField(TEXT("pixels"), Points) || Points->IsEmpty())
        {
            StartupError = TEXT("Fixture requires unique id, integer startChannel >= 1, and nonempty pixels.");
            return false;
        }
        Ids.Add(Id);
        const int32 First = int32(Start) - 1;
        const int64 End = int64(First) + int64(Points->Num()) * 3;
        if (End > MaxChannelCount)
        {
            StartupError = TEXT("Layout exceeds MaxChannelCount.");
            return false;
        }
        for (int32 Channel = First; Channel < End; ++Channel)
        {
            if (Occupied[Channel])
            {
                StartupError = TEXT("Fixture channel ranges overlap.");
                return false;
            }
            Occupied[Channel] = true;
        }
        for (int32 Index = 0; Index < Points->Num(); ++Index)
        {
            const TArray<TSharedPtr<FJsonValue>>* XYZ = nullptr;
            if (!(*Points)[Index].IsValid() || !(*Points)[Index]->TryGetArray(XYZ) || XYZ->Num() != 3)
            {
                StartupError = TEXT("Pixel must be an [x, y, z] triple in meters.");
                return false;
            }
            double Coordinate[3];
            for (int32 Axis = 0; Axis < 3; ++Axis)
            {
                if (!(*XYZ)[Axis].IsValid() || !(*XYZ)[Axis]->TryGetNumber(Coordinate[Axis])
                    || !FMath::IsFinite(Coordinate[Axis]) || FMath::Abs(Coordinate[Axis]) > 10000)
                {
                    StartupError = TEXT("Pixel coordinates must be finite numbers within 10 km.");
                    return false;
                }
            }
            // Browser world: X horizontal, Y up, Z toward viewer. UE uses centimeters and Z up.
            Positions.Emplace(Coordinate[2] * 100, Coordinate[0] * 100, Coordinate[1] * 100);
            Channels.Add(First + Index * 3);
        }
        ChannelCount = FMath::Max(ChannelCount, int32(End));
    }
    double DeclaredCount = 0;
    if (Document->HasField(TEXT("channelCount")))
    {
        if (!Document->TryGetNumberField(TEXT("channelCount"), DeclaredCount)
            || !FMath::IsFinite(DeclaredCount) || DeclaredCount < ChannelCount
            || DeclaredCount > MaxChannelCount || DeclaredCount != double(int32(DeclaredCount)))
        {
            StartupError = TEXT("channelCount must be an integer covering all fixture channels within MaxChannelCount.");
            return false;
        }
        ChannelCount = int32(DeclaredCount);
    }
    if (!LoadScene(Document)) return false;
    PixelChannels = MoveTemp(Channels);
    Frame.Reset(ChannelCount);
    const FVector Scale(PixelRadiusCentimeters / 50.0f); // Engine sphere has 50 cm radius.
    for (const FVector& Position : Positions) Pixels->AddInstance(FTransform(FQuat::Identity, Position, Scale));
    return true;
}

bool ALightShowActor::LoadScene(const TSharedPtr<FJsonObject>& Document)
{
    SceneObjects.Reset();
    bHasAuthoredScene = Document->HasField(TEXT("scene"));
    if (!bHasAuthoredScene) return true;
    const TSharedPtr<FJsonObject>* Scene = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Objects = nullptr;
    double Version = 0;
    if (!Document->TryGetObjectField(TEXT("scene"), Scene) || !Scene->IsValid()
        || !(*Scene)->TryGetNumberField(TEXT("version"), Version) || Version != 1
        || !(*Scene)->TryGetArrayField(TEXT("objects"), Objects) || Objects->Num() > 100)
    {
        StartupError = TEXT("Scene requires version 1 and at most 100 objects.");
        return false;
    }
    const TSharedPtr<FJsonObject>* Environment = nullptr;
    if ((*Scene)->HasField(TEXT("environment")))
    {
        if (!(*Scene)->TryGetObjectField(TEXT("environment"), Environment) || !Environment->IsValid()
            || !(*Environment)->TryGetBoolField(TEXT("groundVisible"), bSceneGroundVisible)
            || !ReadHexColor(*Environment, TEXT("groundColor"), SceneGroundColor))
        {
            StartupError = TEXT("Scene environment requires groundVisible and #RRGGBB groundColor.");
            return false;
        }
    }
    TSet<FString> Ids;
    for (const TSharedPtr<FJsonValue>& Value : *Objects)
    {
        if (!Value.IsValid() || Value->Type != EJson::Object)
        {
            StartupError = TEXT("Every scene object must be an object.");
            return false;
        }
        const TSharedPtr<FJsonObject> Object = Value->AsObject();
        FLightShowSceneObject Parsed;
        if (!Object->TryGetStringField(TEXT("id"), Parsed.Id) || Parsed.Id.IsEmpty() || Ids.Contains(Parsed.Id)
            || !Object->TryGetStringField(TEXT("type"), Parsed.Type)
            || (Parsed.Type != TEXT("house") && Parsed.Type != TEXT("pine") && Parsed.Type != TEXT("box")
                && Parsed.Type != TEXT("cone") && Parsed.Type != TEXT("arch") && Parsed.Type != TEXT("arches"))
            || !ReadTriple(Object, TEXT("position"), Parsed.Position, -1000, 1000)
            || !ReadTriple(Object, TEXT("rotation"), Parsed.Rotation, -360, 360)
            || !ReadTriple(Object, TEXT("scale"), Parsed.Scale, .001, 1000)
            || !ReadHexColor(Object, TEXT("color"), Parsed.Color))
        {
            StartupError = TEXT("Scene objects require unique id, supported type, finite transform, positive scale and #RRGGBB color.");
            return false;
        }
        Ids.Add(Parsed.Id);
        SceneObjects.Add(MoveTemp(Parsed));
    }
    return true;
}

bool ALightShowActor::OpenSocket()
{
    if (ListenPort < 1 || ListenPort > 65535)
    {
        StartupError = TEXT("DDP port must be between 1 and 65535.");
        return false;
    }
    ISocketSubsystem* Subsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
    if (!Subsystem)
    {
        StartupError = TEXT("No platform socket subsystem.");
        return false;
    }
    TSharedRef<FInternetAddr> Address = Subsystem->CreateInternetAddr();
    bool bValid = false;
    Address->SetIp(*BindAddress, bValid);
    Address->SetPort(ListenPort);
    if (!bValid)
    {
        StartupError = TEXT("DDP bind address must be an IPv4 address.");
        return false;
    }
    Socket = Subsystem->CreateSocket(NAME_DGram, TEXT("ChristmasLightsDDP"), false);
    if (!Socket || !Socket->SetNonBlocking(true) || !Socket->Bind(*Address))
    {
        StartupError = FString::Printf(TEXT("Cannot bind DDP %s:%d; close other receivers on this port."), *BindAddress, ListenPort);
        CloseSocket();
        return false;
    }
    int32 ActualBufferSize = 0;
    Socket->SetReceiveBufferSize(2 * 1024 * 1024, ActualBufferSize);
    ReceiveBuffer.SetNumUninitialized(65507);
    UE_LOG(LogTemp, Display, TEXT("ChristmasLights: %d pixels / %d channels; listening on %s:%d"),
        GetPixelCount(), GetChannelCount(), *BindAddress, ListenPort);
    return true;
}

void ALightShowActor::CloseSocket()
{
    if (Socket)
    {
        Socket->Close();
        if (ISocketSubsystem* Subsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)) Subsystem->DestroySocket(Socket);
        Socket = nullptr;
    }
}

void ALightShowActor::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!Socket) return;
    const double Now = FPlatformTime::Seconds();
    // Discard an incomplete transaction even if no more datagrams arrive.
    if (Frame.HasPending() && Now - PendingStartTime > PendingTimeoutSeconds) Frame.DiscardPending();
    bool bChanged = false;
    for (int32 PacketIndex = 0; PacketIndex < MaxPacketsPerTick; ++PacketIndex)
    {
        uint32 PendingBytes = 0;
        if (!Socket->HasPendingData(PendingBytes)) break;
        int32 Read = 0;
        if (!Socket->Recv(ReceiveBuffer.GetData(), ReceiveBuffer.Num(), Read)) break;
        ++ReceivedPackets;
        const bool bWasPending = Frame.HasPending();
        FString Error;
        const EDdpResult Result = Frame.Accept(ReceiveBuffer.GetData(), Read, Error);
        if (Result == EDdpResult::Rejected)
        {
            ++RejectedPackets;
            // A malformed chunk must not leak into a later transaction.
            Frame.DiscardPending();
            continue;
        }
        LastPacketTime = Now;
        if (!bWasPending && Frame.HasPending()) PendingStartTime = Now;
        if (Result == EDdpResult::Committed)
        {
            ++CommittedFrames;
            LastFrameTime = Now;
            bChanged = true;
        }
    }
    // Socket work and UObject writes both run on the game thread. Apply only the newest complete frame this tick.
    if (bChanged) ApplyFrame();
}

void ALightShowActor::ApplyFrame()
{
    const TArray<uint8>& Channels = Frame.GetChannels();
    for (int32 Pixel = 0; Pixel < PixelChannels.Num(); ++Pixel)
    {
        const int32 First = PixelChannels[Pixel];
        const FLinearColor Color = FLinearColor::FromSRGBColor(FColor(Channels[First], Channels[First + 1], Channels[First + 2]));
        Pixels->SetCustomDataValue(Pixel, 0, Color.R, false);
        Pixels->SetCustomDataValue(Pixel, 1, Color.G, false);
        Pixels->SetCustomDataValue(Pixel, 2, Color.B, false);
    }
    Pixels->MarkRenderStateDirty();
}

void ALightShowActor::AddBox(const FVector& Location, const FVector& Size, const FRotator& Rotation)
{
    UStaticMeshComponent* Box = NewObject<UStaticMeshComponent>(this);
    AddInstanceComponent(Box);
    Box->SetMobility(EComponentMobility::Movable);
    Box->SetupAttachment(GetRootComponent());
    Box->SetStaticMesh(CubeMesh);
    Box->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Box->SetRelativeLocationAndRotation(Location, Rotation);
    Box->SetRelativeScale3D(Size / 100.0);
    if (SceneryMaterial) Box->SetMaterial(0, SceneryMaterial);
    Box->RegisterComponent();
}

void ALightShowActor::BuildScenery()
{
    if (bHasAuthoredScene)
    {
        if (bSceneGroundVisible)
        {
            FLightShowSceneObject Ground;
            Ground.Id = TEXT("Ground"); Ground.Type = TEXT("box");
            Ground.Position = FVector(0, -.105, 0); Ground.Scale = FVector(120, .04, 120);
            Ground.Color = SceneGroundColor;
            BuildSceneObject(Ground);
        }
        for (const FLightShowSceneObject& Object : SceneObjects) BuildSceneObject(Object);
        return;
    }
    // Inset scenery from the fixture surfaces, including both side eaves.
    // Front X=-5 cm, sides Y=+/-395 cm; all sample bulb spheres remain outside.
    AddBox(FVector(-200, 0, 175), FVector(390, 790, 350));
    // Unreal's positive Roll rotates local +Y toward -Z.
    AddBox(FVector(-200, -195, 468), FVector(390, 450, 12), FRotator(0, 0, -29.9));
    AddBox(FVector(-200, 195, 468), FVector(390, 450, 12), FRotator(0, 0, 29.9));
    AddBox(FVector(0, 0, -15), FVector(3000, 4000, 25));
    // A post defines the mega tree; the wire cone is represented by its actual pixels.
    AddBox(FVector(125, 650, 300), FVector(5, 5, 600));
}

void ALightShowActor::BuildSceneObject(const FLightShowSceneObject& Object)
{
    FSceneMeshBuilder Builder;
    const FLinearColor Trim = FLinearColor::FromSRGBColor(FColor(171, 185, 197));
    const FLinearColor Snow = FLinearColor::FromSRGBColor(FColor(199, 214, 229));
    const FLinearColor Dark = FLinearColor::FromSRGBColor(FColor(30, 46, 61));
    if (Object.Type == TEXT("box")) Builder.Box(FVector(0, .5, 0), FVector::OneVector, Object.Color);
    else if (Object.Type == TEXT("cone")) Builder.Cone(0, 1, .5, Object.Color);
    else if (Object.Type == TEXT("pine"))
    {
        Builder.Box(FVector(0, .09, 0), FVector(.09, .18, .09), Dark);
        const FVector Layers[] = {FVector(.1, .58, .5), FVector(.32, .47, .37), FVector(.62, .38, .24)};
        for (int32 Index = 0; Index < 3; ++Index)
        {
            const FVector& Layer = Layers[Index];
            Builder.Cone(Layer.X, Layer.Y, Layer.Z, Object.Color);
            Builder.Cone(Layer.X + Layer.Y * .25, Layer.Y * .75, Layer.Z * .74, Snow);
        }
    }
    else if (Object.Type == TEXT("arch")) Builder.Arch(0, 1, 1, Object.Color);
    else if (Object.Type == TEXT("arches"))
    {
        for (const double Center : {-2.3, 0.0, 2.3}) Builder.Arch(Center, 2, 1.2, Object.Color);
    }
    else if (Object.Type == TEXT("house"))
    {
        Builder.Box(FVector(0, 1.75, -2), FVector(8, 3.5, 4), Object.Color);
        Builder.Triangle(FVector(-4, 3.5, -.02), FVector(0, 5.8, -.02), FVector(4, 3.5, -.02), Object.Color);
        Builder.Triangle(FVector(4, 3.5, -4), FVector(0, 5.8, -4), FVector(-4, 3.5, -4), Object.Color);
        Builder.Quad(FVector(-3.98, 3.49, -.02), FVector(0, 5.79, -.02),
            FVector(0, 5.79, -3.98), FVector(-3.98, 3.49, -3.98), Snow);
        Builder.Quad(FVector(0, 5.79, -.02), FVector(3.98, 3.49, -.02),
            FVector(3.98, 3.49, -3.98), FVector(0, 5.79, -3.98), Snow);
        Builder.Box(FVector(-3.96, 1.75, .07), FVector(.17, 3.5, .16), Trim);
        Builder.Box(FVector(3.96, 1.75, .07), FVector(.17, 3.5, .16), Trim);
        Builder.Box(FVector(0, .1, .06), FVector(8.2, .18, .15), Trim);
        Builder.Box(FVector(2.5, 5.02, -2.4), FVector(.7, 1.3, .8), Dark);
        Builder.Box(FVector(2.5, 5.7, -2.4), FVector(.86, .13, .96), Snow);
        const FLinearColor Window = FLinearColor::FromSRGBColor(FColor(190, 167, 124));
        for (const double X : {-2.3, 2.3})
        {
            Builder.Box(FVector(X, 2, .019), FVector(1.68, 1.58, .035), Trim);
            Builder.Box(FVector(X, 2, .047), FVector(1.48, 1.38, .018), Window);
            Builder.Box(FVector(X, 2, .062), FVector(.045, 1.38, .018), Dark);
            Builder.Box(FVector(X, 2, .062), FVector(1.48, .045, .018), Dark);
            Builder.Box(FVector(X, 1.18, .02), FVector(1.84, .08, .1), Snow);
        }
        Builder.Box(FVector(0, 1.215, .019), FVector(1.3, 2.43, .035), Trim);
        Builder.Box(FVector(0, 1.17, .047), FVector(1.13, 2.3, .025), Dark);
        Builder.Box(FVector(0, 1.8, .065), FVector(.83, .66, .018), Window);
        Builder.Box(FVector(0, .02, .52), FVector(1.8, .12, .8), Snow);
    }
    if (Builder.Vertices.IsEmpty()) return;
    for (FVector& Vertex : Builder.Vertices) Vertex = ChristmasScenePointToUnreal(Vertex, Object);
    TArray<FVector> Normals;
    Normals.SetNumUninitialized(Builder.Vertices.Num());
    for (int32 Index = 0; Index < Builder.Vertices.Num(); Index += 3)
    {
        const FVector Normal = FVector::CrossProduct(Builder.Vertices[Index + 1] - Builder.Vertices[Index],
            Builder.Vertices[Index + 2] - Builder.Vertices[Index]).GetSafeNormal();
        Normals[Index] = Normals[Index + 1] = Normals[Index + 2] = Normal;
    }
    UProceduralMeshComponent* Mesh = NewObject<UProceduralMeshComponent>(this);
    AddInstanceComponent(Mesh);
    Mesh->SetMobility(EComponentMobility::Movable);
    Mesh->SetupAttachment(GetRootComponent());
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Mesh->CreateMeshSection_LinearColor(0, Builder.Vertices, Builder.Triangles, Normals,
        TArray<FVector2D>(), Builder.Colors, TArray<FProcMeshTangent>(), false);
    if (SceneryMaterial)
    {
        UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(SceneryMaterial, this);
        Material->SetVectorParameterValue(TEXT("Color"), FLinearColor::White);
        Mesh->SetMaterial(0, Material);
    }
    Mesh->RegisterComponent();
}

bool ALightShowActor::IsReceiving() const
{
    return LastFrameTime > 0 && FPlatformTime::Seconds() - LastFrameTime <= SignalTimeoutSeconds;
}

FString ALightShowActor::GetStatus() const
{
    if (!StartupError.IsEmpty()) return StartupError;
    const TCHAR* State = IsReceiving() ? TEXT("LIVE") : (CommittedFrames ? TEXT("SIGNAL IDLE - holding last frame") : TEXT("WAITING FOR DDP"));
    return FString::Printf(TEXT("%s  |  %s:%d  |  %d pixels / %d channels\n%s  |  frames %llu  |  datagrams %llu  |  rejected %llu"),
        *LayoutName, *BindAddress, ListenPort, GetPixelCount(), GetChannelCount(), State,
        static_cast<unsigned long long>(CommittedFrames), static_cast<unsigned long long>(ReceivedPackets),
        static_cast<unsigned long long>(RejectedPackets));
}

void ALightShowActor::EndPlay(const EEndPlayReason::Type Reason)
{
    CloseSocket();
    Super::EndPlay(Reason);
}

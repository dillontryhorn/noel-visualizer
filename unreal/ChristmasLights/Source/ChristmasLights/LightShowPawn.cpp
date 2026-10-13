#include "LightShowPawn.h"

#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "Components/SceneComponent.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"

ALightShowPawn::ALightShowPawn()
{
    USceneComponent* Scene = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Scene);
    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
    Camera->SetupAttachment(Scene);
    Camera->bUsePawnControlRotation = true;
    Camera->FieldOfView = 60;
    Camera->PostProcessSettings.bOverride_AutoExposureMinBrightness = true;
    Camera->PostProcessSettings.bOverride_AutoExposureMaxBrightness = true;
    Camera->PostProcessSettings.AutoExposureMinBrightness = 1;
    Camera->PostProcessSettings.AutoExposureMaxBrightness = 1;
    Camera->PostProcessSettings.bOverride_BloomIntensity = true;
    Camera->PostProcessSettings.BloomIntensity = 0.8f;
    Movement = CreateDefaultSubobject<UFloatingPawnMovement>(TEXT("Movement"));
    Movement->MaxSpeed = 750;
    Movement->Acceleration = 2500;
    Movement->Deceleration = 2500;
}

void ALightShowPawn::BeginPlay()
{
    Super::BeginPlay();
    Overview();
}

void ALightShowPawn::PossessedBy(AController* NewController)
{
    Super::PossessedBy(NewController);
    Overview();
    if (APlayerController* Player = Cast<APlayerController>(GetController()))
    {
        Player->SetInputMode(FInputModeGameOnly());
        Player->bShowMouseCursor = false;
    }
}

void ALightShowPawn::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    Input->BindAxis(TEXT("MoveForward"), this, &ALightShowPawn::Forward);
    Input->BindAxis(TEXT("MoveRight"), this, &ALightShowPawn::Right);
    Input->BindAxis(TEXT("MoveUp"), this, &ALightShowPawn::Up);
    Input->BindAxis(TEXT("Turn"), this, &ALightShowPawn::Turn);
    Input->BindAxis(TEXT("LookUp"), this, &ALightShowPawn::Look);
    Input->BindAction(TEXT("Overview"), IE_Pressed, this, &ALightShowPawn::Overview);
}

void ALightShowPawn::Forward(float Value) { AddMovementInput(Camera->GetForwardVector(), Value); }
void ALightShowPawn::Right(float Value) { AddMovementInput(Camera->GetRightVector(), Value); }
void ALightShowPawn::Up(float Value) { AddMovementInput(FVector::UpVector, Value); }
void ALightShowPawn::Turn(float Value) { AddControllerYawInput(Value); }
void ALightShowPawn::Look(float Value) { AddControllerPitchInput(Value); }

void ALightShowPawn::Overview()
{
    const FVector Location(2050, 350, 850);
    const FRotator Rotation = (FVector(0, 180, 240) - Location).Rotation();
    SetActorLocationAndRotation(Location, Rotation);
    if (GetController()) GetController()->SetControlRotation(Rotation);
    Movement->StopMovementImmediately();
}

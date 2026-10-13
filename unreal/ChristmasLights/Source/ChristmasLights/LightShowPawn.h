#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "LightShowPawn.generated.h"

class UCameraComponent;
class UFloatingPawnMovement;

UCLASS()
class CHRISTMASLIGHTS_API ALightShowPawn : public APawn
{
    GENERATED_BODY()
public:
    ALightShowPawn();
    virtual void BeginPlay() override;
    virtual void PossessedBy(AController* NewController) override;
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override;

private:
    void Forward(float Value);
    void Right(float Value);
    void Up(float Value);
    void Turn(float Value);
    void Look(float Value);
    void Overview();
    UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> Camera;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UFloatingPawnMovement> Movement;
};

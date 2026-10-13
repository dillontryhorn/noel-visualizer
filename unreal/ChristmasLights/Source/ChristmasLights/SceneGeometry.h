#pragma once

#include "CoreMinimal.h"

// Browser-space transforms: meters, Y up, Euler XYZ angles in degrees.
struct FLightShowSceneObject
{
    FString Id;
    FString Type;
    FVector Position = FVector::ZeroVector;
    FVector Rotation = FVector::ZeroVector;
    FVector Scale = FVector::OneVector;
    FLinearColor Color = FLinearColor::White;
};

CHRISTMASLIGHTS_API FVector ChristmasScenePointToUnreal(const FVector& Local, const FLightShowSceneObject& Object);

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "LightShowGameMode.generated.h"

UCLASS()
class CHRISTMASLIGHTS_API ALightShowGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ALightShowGameMode();
    virtual void BeginPlay() override;
};

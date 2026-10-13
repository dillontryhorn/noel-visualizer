#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "LightShowHud.generated.h"

class ALightShowActor;

UCLASS()
class CHRISTMASLIGHTS_API ALightShowHud : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
private:
    TWeakObjectPtr<ALightShowActor> Show;
};

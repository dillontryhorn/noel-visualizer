#include "LightShowGameMode.h"

#include "Engine/World.h"
#include "EngineUtils.h"
#include "LightShowActor.h"
#include "LightShowHud.h"
#include "LightShowPawn.h"

ALightShowGameMode::ALightShowGameMode()
{
    DefaultPawnClass = ALightShowPawn::StaticClass();
    HUDClass = ALightShowHud::StaticClass();
}

void ALightShowGameMode::BeginPlay()
{
    Super::BeginPlay();
    for (TActorIterator<ALightShowActor> It(GetWorld()); It; ++It) return;
    GetWorld()->SpawnActor<ALightShowActor>();
}

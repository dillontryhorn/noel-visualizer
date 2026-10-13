#include "LightShowHud.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "LightShowActor.h"

void ALightShowHud::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas) return;
    if (!Show.IsValid())
    {
        for (TActorIterator<ALightShowActor> It(GetWorld()); It; ++It) { Show = *It; break; }
    }
    DrawRect(FLinearColor(0.005f, 0.01f, 0.02f, 0.85f), 12, 12, FMath::Min(900.0f, Canvas->ClipX - 24), 98);
    DrawText(TEXT("CHRISTMAS LIGHT SHOW / UNREAL DDP TEST"), FLinearColor(0.8f, 0.95f, 1), 24, 20, GEngine->GetMediumFont(), 1);
    DrawText(Show.IsValid() ? Show->GetStatus() : TEXT("Starting visualizer..."), FLinearColor::White, 24, 44, GEngine->GetSmallFont(), 1);
    DrawText(TEXT("WASD fly  |  Mouse look  |  Q / E down / up  |  Home overview  |  Shift+F1 release mouse (Editor)"),
        FLinearColor(0.6f, 0.7f, 0.8f), 24, 88, GEngine->GetSmallFont(), 1);
}

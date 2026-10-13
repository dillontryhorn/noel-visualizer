using UnrealBuildTool;

public class ChristmasLightsTarget : TargetRules
{
    public ChristmasLightsTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_6;
        ExtraModuleNames.Add("ChristmasLights");
    }
}

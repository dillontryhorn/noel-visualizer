using UnrealBuildTool;

public class ChristmasLightsEditorTarget : TargetRules
{
    public ChristmasLightsEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_6;
        ExtraModuleNames.Add("ChristmasLights");
    }
}

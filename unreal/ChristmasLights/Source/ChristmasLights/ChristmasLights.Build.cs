using UnrealBuildTool;

public class ChristmasLights : ModuleRules
{
    public ChristmasLights(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] {
            "Core", "CoreUObject", "Engine", "InputCore", "Sockets", "Networking", "Json", "ProceduralMeshComponent"
        });
    }
}

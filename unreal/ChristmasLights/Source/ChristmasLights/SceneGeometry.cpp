#include "SceneGeometry.h"

FVector ChristmasScenePointToUnreal(const FVector& Local, const FLightShowSceneObject& Object)
{
    // Three.js's default Euler XYZ matrix, applied after local scale. Geometry is
    // baked to preserve shear from nonuniform scale, including sloped roof panels.
    const FVector P = Local * Object.Scale;
    const double X = FMath::DegreesToRadians(Object.Rotation.X);
    const double Y = FMath::DegreesToRadians(Object.Rotation.Y);
    const double Z = FMath::DegreesToRadians(Object.Rotation.Z);
    const double A = FMath::Cos(X), B = FMath::Sin(X), C = FMath::Cos(Y), D = FMath::Sin(Y);
    const double E = FMath::Cos(Z), F = FMath::Sin(Z);
    const FVector World(
        C * E * P.X - C * F * P.Y + D * P.Z,
        (A * F + B * E * D) * P.X + (A * E - B * F * D) * P.Y - B * C * P.Z,
        (B * F - A * E * D) * P.X + (B * E + A * F * D) * P.Y + A * C * P.Z);
    const FVector Placed = World + Object.Position;
    return FVector(Placed.Z, Placed.X, Placed.Y) * 100.0;
}

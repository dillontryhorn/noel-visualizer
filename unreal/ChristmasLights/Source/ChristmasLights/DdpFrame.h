#pragma once

#include "CoreMinimal.h"

enum class EDdpResult : uint8 { Rejected, Buffered, Committed };

/** Game-thread-only DDP v1 RGB assembler. Offsets and lengths are bytes. */
class FDdpFrame
{
public:
    explicit FDdpFrame(int32 ChannelCount = 0);
    void Reset(int32 ChannelCount);
    EDdpResult Accept(const uint8* Data, int32 Size, FString& Error);
    void DiscardPending();
    const TArray<uint8>& GetChannels() const { return Channels; }
    bool HasPending() const { return bPending; }

private:
    TArray<uint8> Channels;
    TArray<uint8> Pending;
    bool bPending = false;
};

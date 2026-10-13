MATLAB can generate the same standard DDP RGB packets consumed by the browser bridge and Unreal project. This optional test uses MATLAB's Java interface and requires no Instrument Control Toolbox or Unreal simulation toolbox.

From the repository root, after starting the Python visualizer and putting Unreal in Play mode:

```powershell
$env:MATLAB_JAVA = 'C:\Program Files\Java\jdk-21.0.10'
& 'C:\Program Files\MATLAB\R2026b\bin\matlab.exe' -batch "addpath('matlab'); test_ddp_packets; send_light_show(10)"
```

Adapt the Java path to a supported installation. The example path exists on this machine. R2026b no longer includes Java; [MathWorks lists the supported OpenJDK versions](https://www.mathworks.com/support/requirements/openjdk.html). The `MATLAB_JAVA` environment variable enables Java for MATLAB launched from this shell without changing the user's persisted MATLAB configuration. Alternatively, configure Java with MathWorks' [`jenv` instructions](https://www.mathworks.com/help/matlab/matlab_external/configure-your-system-to-use-java.html).

Select **Live input** in the browser before running the sender. The default route is MATLAB -> UDP 4048 -> Python -> UDP 4049 -> Unreal. For a direct Unreal test, stop the Python relay and call `send_light_show(10, 4049)`. Both viewers hold the last complete DDP frame; this sender finishes with a blackout frame.

The local serialization checks can run independently: `addpath('matlab'); test_ddp_packets`. MATLAB must start with Java enabled for UDP transmission. The MATLAB sender is a test client for the included Unreal C++ project; it does not require MathWorks' separate Unreal Engine integration products.

For a loopback transmission check independent of the bridge or Unreal, start `python matlab/verify_udp_capture.py` in one terminal, then run `send_light_show(0.2, 4059)` from MATLAB in another. The Python receiver verifies RGB packet headers, byte offsets, per-packet sequence progression, complete fixture coverage, and the final blackout.

Validation on this machine: R2026b passed the local serializer checks. With the installed Java 21 runtime selected through `MATLAB_JAVA`, the loopback check captured 21 UDP datagrams forming six rainbow frames and one blackout frame, all covering 4,275 channels. Unreal compilation and rendering require a separate installed engine and remain unverified here.

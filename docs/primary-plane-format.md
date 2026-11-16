# X5 primary-plane format selection

The board log at 921.695 seconds reports an atomic core rejection:
`[PLANE:63:Primary] invalid pixel format AR24`, after binding that plane to
`[CRTC:62:crtc-bt1120]`. The framebuffer is the software compositor's BGRA_8888
client target, represented by DRM_FORMAT_ARGB8888. Encoder routing capability
alone does not establish that a pipeline can scan out this format.

Patch 0006 uses the kernel-advertised plane formats. X5 GetDrmPlane excludes
primary planes without ARGB8888. After resource enumeration, CRTCs lacking a
compatible primary plane are removed from the compositor's candidate map.
Startup and hotplug use that same map. No object IDs or resource enumeration
order are assumed. Non-X5 selection remains unchanged. This checks format
support; mode, DMA import, modifiers and actual scanout still require the
kernel atomic validation and physical testing.

The same capture identifies USB 0484:5750 QDtech MPI5001, successfully bound
to hid-multitouch with event1 created. This establishes kernel enumeration,
not emitted coordinates, multitouch tracking, display mapping or UI delivery.
Use `/rdkhm/touch-status.sh` for inventory; event numbers may change across boots.

The input udriver previously recognized touch only by `input_mt_wrapper` in
the name. Input patch 0001 reads EVIOCGPROP and event capabilities, recognizes
INPUT_PROP_DIRECT devices with paired MT or legacy absolute coordinates, and
preserves existing name-based fallbacks. It also fixes ABS range enumeration:
the old loop used bitmap word indices as axis codes, omitting MT coordinates.
Nine host classifier fixtures cover direct MT/single-touch, incomplete or
indirect capabilities, and legacy keyboard/mouse/touchpad/touch names. Actual
MPI5001 capability bits and application delivery remain board checks.

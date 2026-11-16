# Primary-plane zpos validation

The latest board capture still reports EINVAL from the first atomic commit.
With error propagation in patch 0004, the failed display is no longer announced
and HDMI correctly remains disabled. This capture lists 800x480 first, unlike
the previous 1080p display; the parameter bug below is independent of resolution.

`HdiLayer::mZorder` initializes to unsigned -1 (4294967295). Normal composition
sets the client layer's zorder in PrepareDisplayLayers, but PushFirstFrame runs
before that path. ApplyPlane previously passed this sentinel to DRM zpos.
The X5 DC8000 Nano primary-plane description specifies zpos {min=0,max=2,val=0},
and the kernel registers it as a bounded property. The first-frame sentinel is
invalid. Later logical application zorders can also exceed the hardware range.

Patch 0005 leaves zpos at its kernel default for X5's single composed primary
plane. Application ordering remains the software compositor's responsibility.
Other backends retain their existing behavior.

The initial atomic mock incorrectly returned zorder zero and did not validate
the property range, so it missed this bug. The corrected mock uses the real
sentinel and rejects out-of-range zpos on commit: the pre-fix production code
fails its first-frame assertion; patched production code passes. Tests also
verify that X5 no longer submits zpos. This reproduces a concrete invalid
parameter but does not prove that no other physical DRM constraint remains.

The ARM64 images build succeeded. SD verification passed all 38 required
composer exports, 134 packaged artifact comparisons, the MBR, checksum and
four filesystems. Logs: `out/logs/build-primary-zpos.log` and
`out/logs/image-primary-zpos.log`. The image SHA256 is
`f8f3e79bfc05d597aa0bad03999bb097a203c013491194971ca69af8cd2c9de4`.
Board validation of this image is pending.

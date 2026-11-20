# X5 model conversion

How to turn an ONNX model into an X5 BPU artifact, and the current state of the
toolchain in this workspace.

## Status

| Item | State |
| --- | --- |
| OE X5 package | downloaded and extracted |
| Host prerequisites | Python 3.10.12, gcc/g++ 11.4.0, graphviz present |
| Python wheels installed | yes (`thirdparty/toolchains/oe_x5/venv`) |
| ONNX conversion executed | yes (ResNet18, 2026-11-20) |
| Precompiled model tested on board | yes (MobileNetV2) |

The runtime cannot execute ONNX. PTQ produces `.bin`; QAT produces `.hbm`.
The board test used a precompiled PTQ `.bin` from the official model zoo.

## ResNet18 conversion executed (2026-11-20)

The toolchain was installed into `thirdparty/toolchains/oe_x5/venv` and used to
convert a real ONNX model.

- ONNX: ONNX Model Zoo ResNet18 v1
  - URL: `https://github.com/onnx/models/raw/main/validated/vision/classification/resnet/model/resnet18-v1-7.onnx`
  - Local: `thirdparty/toolchains/oe_x5/work/resnet18/resnet18-v1-7.onnx`
  - SHA256: `4e8f8653e7a2222b3904cc3fe8e304cd8b339ce1d05fd24688162f86fb6df52c`
- Calibration: 100 ImageNet JPEGs converted to float32 RGB
  (`calibration_data_rgb_f32`).
- Config: `work/resnet18/resnet18_config.yaml`, input `1x3x224x224`,
  `input_type_rt: nv12`, ImageNet mean/scale, `march: bayes-e`.

Commands:

```sh
hb_mapper checker --model-type onnx --model resnet18-v1-7.onnx \
  --march bayes-e --input-shape data 1x3x224x224
hb_mapper makertbin --config resnet18_config.yaml --model-type onnx
```

Checker: all convolutions on BPU, only the final reshape on CPU.
Output: `work/resnet18/model_output/resnet18_224x224_nv12.bin` (11 MiB).

Board result (`out/board-logs/20261120-npu/resnet18.log`):

- `model_info`: input NV12 `(1,3,224,224)`, output F32 `(1,1000,1,1)`,
  no HBRT/model version warning.
- `perf --frame_count 200 --thread_num 1`: 3.17 ms average, 314 FPS.
- `infer` on the constant NV12 input: class 473, score 3.48113.
- Private daemon: `top=473`, `value=3.481126`, same result.

Toolchain installation notes:

- The OE sample model downloader failed against its FTP server (`425`); an ONNX
  Model Zoo file plus the bundled ImageNet calibration set was used instead.
- `pycocotools==2.0.3` failed to build with the newer numpy; `2.0.7` was used.
- `setuptools==65.5.1` is required for `hbdk-config` (`pkg_resources`).
- `horizon_nn` imports torch at load time; CPU torch `1.13.0` was installed.

## Toolchain package

- URL: `https://d-robotics-aitoolchain.oss-cn-beijing.aliyuncs.com/oe_x5/1.2.8/D-Robotics_x5_open_explorer_v1.2.8-py310_20240926.tar.gz`
- Archive: `thirdparty/downloads/D-Robotics_x5_open_explorer_v1.2.8-py310_20240926.tar.gz`
- SHA256: `78f3d677295d5674e40d08cff758d4fde9f591d1fc11da3dd148b3c15a561c21`
- Extracted: `thirdparty/toolchains/oe_x5/`
- The archive is XZ-compressed despite the `.tar.gz` name; extract with
  `tar -xf`.

Key contents:

```text
package/host/ai_toolchain/
  hbdk-3.49.15-cp310-cp310-linux_x86_64.whl
  hbdk_model_verifier-3.49.15-py3-none-linux_x86_64.whl
  horizon_nn-1.1.0-cp310-cp310-linux_x86_64.whl
  horizon_tc_ui-1.24.3-cp310-cp310-linux_x86_64.whl   # hb_mapper
  horizon_plugin_pytorch-2.3.6+cu116.torch1130-...whl # QAT
  install_ai_toolchain.sh
  requirements.txt
package/host/hrt_tools/hrt_model_exec               # x86_64
package/board/hrt_tools/bin/hrt_model_exec           # aarch64
samples/ai_toolchain/horizon_model_convert_sample/
```

`hbdk` and `horizon_tc_ui` are cp310 wheels; use Python 3.10.

## Install (not executed)

The official flow is `install_ai_toolchain.sh`; OE recommends its Docker image.
If installing on the host, use a dedicated venv and keep the host Python clean.
The script installs the pinned packages from `requirements.txt`, the wheels
above, and may download torch for QAT. The official Docker images are published
on Docker Hub (`openexplorer/ai_toolchain_ubuntu_20_x5_cpu` and `_gpu`); the
release archive is the host/board package.

Do not install over the system Python used by the rest of the integration
tooling.

## PTQ: ONNX -> `.bin`

The OE sample at
`thirdparty/toolchains/oe_x5/samples/ai_toolchain/horizon_model_convert_sample/03_classification/07_efficientnet_lite2_onnx/`
shows the ONNX flow. Commands:

```sh
cd .../07_efficientnet_lite2_onnx/mapper
./00_init.sh          # optional: download sample ONNX + calibration data
./01_check.sh         # hb_mapper checker
./02_preprocess.sh    # convert calibration images to float32
./03_build.sh         # hb_mapper makertbin
```

The core commands are:

```sh
hb_mapper checker --model-type onnx --model model.onnx --march bayes-e
hb_mapper makertbin --config model_config.yaml --model-type onnx
```

A config starts from the sample YAML and sets:

- `model_parameters.onnx_model`
- `model_parameters.march: bayes-e`
- `model_parameters.working_dir`
- `model_parameters.output_model_file_prefix`
- `input_parameters.input_type_rt: nv12` (board input)
- `input_parameters.input_type_train` / `input_layout_train`
- `input_parameters.input_shape` when the ONNX shape is dynamic
- `calibration_parameters.cal_data_dir` (float32 calibration tensors)
- `calibration_parameters.calibration_type` (for example `max`)
- `compiler_parameters.compile_mode` / `optimize_level`

Output `.bin` files are written under `working_dir`. Use `hb_mapper checker`
first; it reports unsupported operators before any calibration work.

### Calibration data

PTQ needs representative inputs, not just the ONNX file. The sample
`02_preprocess.sh` converts ImageNet images with `data_preprocess.py` into the
`cal_data_dir` layout. For a custom model, prepare your own calibration set in
the same numeric range and layout as `input_type_train`.

## QAT: `.hbm`

QAT uses `horizon_plugin_pytorch` and a trainable PyTorch model:

```text
check_model -> compile_model / export_hbir -> .hbm
```

This is only needed when PTQ accuracy is insufficient. The robot-policy ONNX
files are not QAT-ready; they would first need a matching PyTorch training and
quantization flow. No QAT work has been done in this workspace.

## Precompiled model zoo

For runtime/board verification, use a published `.bin`:

- MobileNetV2:
  `https://archive.d-robotics.cc/downloads/rdk_model_zoo/rdk_x5/mobilenetv2_224x224_nv12.bin`
- SHA256: `3e2b7c46fc3b3a6d07a5326c0b9632fe98fe5ca38835346ab2eedc22ed427158`
- List of samples and conversion notes:
  `https://github.com/D-Robotics/rdk_model_zoo` (branch `rdk_x5`)

## Board verification

Use the aarch64 `hrt_model_exec` through the private loader:

```sh
/vendor/lib64/rdkhm-accelerator/ld-linux-aarch64.so.1 \
  --inhibit-cache --library-path /vendor/lib64/rdkhm-accelerator \
  /data/local/tmp/hrt_model_exec perf \
  --model_file /data/local/tmp/mobilenetv2.bin --frame_count 200 --thread_num 1
```

Observed on 2026-11-20:

- MobileNetV2 PTQ `.bin`, input NV12 `(1,3,224,224)`, output F32
  `(1,1000,1,1)`.
- Perf: 1.514 ms average, 656 FPS, 1 thread, 200 frames.
- Infer on a constant `0x80` NV12 input: class 892, score 0.0739321.
- The private daemon path (`tests/nnrt-infer-client.cpp` / `nnrt-infer-client`)
  returned the same top class and score.
- Log: `out/board-logs/20261120-npu/npu.log`.

The model was built with HBRT 3.15.47.0 while the board runtime is 3.15.55.0.
It ran, but production accuracy requires building with a matching OpenExplorer
package.

## Constraints for the robot-policy ONNX files

The ONNX models elsewhere on the host are locomotion policies, not standard
classification/detection networks. Before conversion:

1. `hb_mapper checker` must accept every operator.
2. Inputs must have fixed shapes or an explicit `input_shape`.
3. A representative calibration set must be exported from the same observation
   distribution.
4. Output post-processing must not depend on CPU-only custom fragments.

If the checker rejects an operator, conversion is blocked until the model is
rewritten or a supported replacement is used.

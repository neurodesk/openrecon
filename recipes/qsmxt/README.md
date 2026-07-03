# QSMxT OpenRecon

This OpenRecon app runs QSMxT Quantitative Susceptibility Mapping (QSM) inline on
the scanner. It is an image-in/image-out app: it receives reconstructed ISMRMRD
image messages, separates the magnitude and phase series, writes a temporary BIDS
MEGRE dataset, runs the QSMxT v9 Rust binary, and sends the selected derivatives
back as derived MRD image series.

This OpenRecon tool is based on QSMxT (https://github.com/QSMxT/QSMxT).

Reference: Stewart AW, Robinson SD, O'Brien K, Jin J, Widhalm G, Hangel G, Walls A,
Goodwin J, Eckstein K, Tourell M, Morgan C, Narayanan A, Barth M, Bollmann S.
"QSMxT: Robust masking and artifact reduction for quantitative susceptibility
mapping". Magnetic Resonance in Medicine 87.3 (2022): 1289-1300.
https://doi.org/10.1002/mrm.29048

## Input Data

Use a plain GRE acquisition with unfiltered phase and magnitude outputs enabled.
Enable both phase and magnitude reconstruction on the sequence.

QSMxT needs unfiltered phase data. SWI sequences that already apply SWI-specific
phase processing or filtering are **not** suitable inputs for this OpenRecon
adapter; for example, `t2_swi_tra_wave4_2mm` does not provide the required
unfiltered phase data and should not be used for QSMxT. Start from a plain GRE
sequence instead.

The wrapper expects one magnitude series and one phase series. It classifies phase
data from MRD image type metadata, DICOM image type metadata, or source series
names such as `phase`, `pha`, or `_Pha`. If explicit metadata is absent and exactly
two series are present, the lower dynamic-range series is used as phase.

Echo grouping, echo times, field strength, and B0 direction are derived from the
incoming MRD image stream and generated NIfTI geometry.

## Parameters

| Parameter id | Type | Default | Description |
| --- | --- | --- | --- |
| `config` | choice | `qsmxt` | Selects this OpenRecon app / the MRD server configuration. |
| `sendoutputs` | choice | `qsm` | Selects which QSMxT derivatives are sent back (QSM only, All available, Magnitude, Mask, SWI, T2\*, R2\*). |
| `sendoriginal` | boolean | `false` | If enabled, returns the original magnitude and phase image series before the derived QSMxT output. |
| `qsmalgorithm` | choice | `rts` | QSMxT dipole-inversion algorithm (RTS, TV, TKD, TSVD, TGV, Tikhonov, NLTV, MEDI, iLSQR, QSMART). |
| `unwrappingalgorithm` | choice | `romeo` | QSMxT phase-unwrapping algorithm (ROMEO, Laplacian). |
| `bfalgorithm` | choice | `pdf` | QSMxT background-field removal algorithm (PDF, VSHARP, LBV, iSMV, SHARP). |
| `maskpreset` | choice | `robust-threshold` | QSMxT masking preset (Robust threshold, BET). |

The scanner UI defaults are set for a robust inline QSM run: only the QSM map is
returned, inversion uses RTS, unwrapping uses ROMEO, background-field removal uses
PDF, and masking uses the robust-threshold preset (which avoids external BET
dependencies). Enable `sendoriginal` only when the original magnitude and phase
series are needed for debugging.

## Outputs

For each derived magnitude/phase echo group the wrapper writes a BIDS MEGRE pair:

```text
sub-01/anat/sub-01_acq-<source>_echo-N_part-mag_MEGRE.nii.gz
sub-01/anat/sub-01_acq-<source>_echo-N_part-phase_MEGRE.nii.gz
```

The default output is the QSM map (`Chimap`), returned as a derived MRD image
series. Set `sendoutputs=all` to return all QSMxT derivatives that exist after the
run (e.g. QSM, magnitude, mask, SWI, T2\*, R2\*). When `sendoriginal` is enabled,
the original magnitude and phase series are sent first, followed by the derived
QSMxT output.

## Open Source Development

The source for this OpenRecon package is in the NeuroContainers repository:
https://github.com/NeuroDesk/neurocontainers/tree/main/recipes/qsmxt

For bugs and feature requests, opening an issue in the NeuroContainers repository
is preferred: https://github.com/NeuroDesk/neurocontainers/issues. Questions can
also be posted in the Neurodesk discussion forum at
https://github.com/orgs/neurodesk/discussions or sent via
https://neurodesk.org/contact/.

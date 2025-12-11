# musclemap VERSION_WILL_BE_REPLACED_BY_SCRIPT

This OpenRecon tool is based on the MuscleMap Toolbox (https://github.com/MuscleMap/MuscleMap)

A free and open-source software toolbox for whole-body muscle segmentation and analysis.

We are currently developing the standardized acquisition protocol for whole-body quantitative MRI of muscle. You can access the Google doc here: https://docs.google.com/document/d/1q7AAnPEr7Rj5gb9d_mLrRnAiav1f32J-RPswvOPk5xE/edit?usp=sharing. To collaborate on the standardized acquisition protocol, please contact us: neuromuscularinsightlab@stanford.edu.

When citing MuscleMap, please cite the following publication:

McKay MJ, Weber KA 2nd, Wesselink EO, Smith ZA, Abbott R, Anderson DB, Ashton-James CE, Atyeo J, Beach AJ, Burns J, Clarke S, Collins NJ, Coppieters MW, Cornwall J, Crawford RJ, De Martino E, Dunn AG, Eyles JP, Feng HJ, Fortin M, Franettovich Smith MM, Galloway G, Gandomkar Z, Glastras S, Henderson LA, Hides JA, Hiller CE, Hilmer SN, Hoggarth MA, Kim B, Lal N, LaPorta L, Magnussen JS, Maloney S, March L, Nackley AG, O'Leary SP, Peolsson A, Perraton Z, Pool-Goudzwaard AL, Schnitzler M, Seitz AL, Semciw AI, Sheard PW, Smith AC, Snodgrass SJ, Sullivan J, Tran V, Valentin S, Walton DM, Wishart LR, Elliott JM. MuscleMap: An Open-Source, Community-Supported Consortium for Whole-Body Quantitative MRI of Muscle. J Imaging. 2024;10(11):262. https://doi.org/10.3390/jimaging10110262


# Parameters

| ID | Label | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `sendoriginal` | Send original images | boolean | `true` | Send a copy of original unmodified images back too |
| `fastmodel` | Fast Model | boolean | `true` | Use a faster model for processing (less accurate) |
| `labeltransform` | Scale labels to lower integer range for DICOM 12BIT | boolean | `true` | Applying label transformation: 3 * (label_in // 10) + (label_in % 10) |
| `bodyregion` | Body Region | choice | `wholebody, abdomen, pelvis, thigh, leg` | Select the body region for segmentation |
| `chunksize` | Chunk Size | string | `auto` | Chunk size between 5 and 200 (or 'auto') |
| `spatialoverlap` | Spatial Overlap | int | `50` | Spatial overlap percentage |
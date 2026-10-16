# VanaDrishti Phase 2: Wildlife Species Recognition

Phase 2 introduces fine-grained zero-shot wildlife species recognition to VanaDrishti using **BioCLIP 2** (`imageomics/bioclip-2`).

---

## 1. Pipeline Architecture

```
Camera Trap Frame / Image
         │
         ▼
MegaDetector V6 (Phase 1)
         │
         ├── Class: "person"  ──► Discard or Ranger Safety Alert (No Species Classification)
         ├── Class: "vehicle" ──► Discard or Anti-Poaching Alert (No Species Classification)
         └── Class: "animal"
                  │
                  ▼
         Crop Bounding Box
                  │
                  ▼
         BioCLIP 2 Classifier (Phase 2)
                  │
                  ▼
         Top-K Species Ranking
```

Species classification is **strictly executed on animal detections only**. Human and vehicle detections bypass species recognition to eliminate unnecessary computation and prevent false biological alerts.

---

## 2. Target Species (Tadoba-Andhari Tiger Reserve)

VanaDrishti configures 10 primary wildlife species inhabiting Central Indian forest reserves:

| Common Name | Scientific Name | Taxon / Niche |
| :--- | :--- | :--- |
| **Bengal tiger** | *Panthera tigris tigris* | Apex Predator |
| **Indian leopard** | *Panthera pardus fusca* | Large Carnivore |
| **chital / spotted deer** | *Axis axis* | Primary Herbivore |
| **sambar deer** | *Rusa unicolor* | Large Herbivore |
| **gaur** | *Bos gaurus* | Megaherbivore (Indian Bison) |
| **sloth bear** | *Melursus ursinus* | Omnivore |
| **wild boar** | *Sus scrofa* | Omnivore / Prey |
| **dhole / Indian wild dog** | *Cuon alpinus* | Pack Hunter |
| **nilgai** | *Boselaphus tragocamelus* | Large Antelope (Blue Bull) |
| **Indian peafowl** | *Pavo cristatus* | Forest Avian Indicator |

---

## 3. Precomputed Text Embeddings & Zero-Shot Classification

To maintain high throughput on CPU/edge environments:
1. At initialization, prompt ensembles incorporating common names, scientific binomials, and camera-trap context templates are encoded once through BioCLIP's text transformer.
2. Prompt feature vectors for each species are averaged and normalized to form unit centroid embeddings $\mathbf{t}_i \in \mathbb{R}^D$.
3. At inference time, only the cropped image is encoded by the vision transformer into $\mathbf{f} \in \mathbb{R}^D$. Dot products $\mathbf{f} \cdot \mathbf{t}_i$ immediately yield cosine similarities without repetitive text re-encoding.

---

## 4. Confidence Scores and Calibration Notice

> [!IMPORTANT]
> **BioCLIP similarity scores are raw cosine similarities.**
> The returned `confidence` values are softmax-normalized scaled logits (using BioCLIP's temperature scale $\approx 100$) intended **strictly for candidate ranking and relative display**.
>
> They are **NOT** calibrated Bayesian posterior probabilities. Do not interpret a softmax confidence of `0.85` as an 85% statistical likelihood without empirical threshold calibration.

---

## 5. Usage Example

```python
import cv2
from ml.species import get_species_classifier

# Initialize singleton (loads weights once)
classifier = get_species_classifier()

# Read animal crop from OpenCV
crop = cv2.imread("animal_crop.jpg")

# Classify crop
result = classifier.classify_crop(crop, top_k=3)
print(result)
# Output:
# {
#     "species": "Bengal tiger",
#     "scientific_name": "Panthera tigris tigris",
#     "confidence": 0.9954,
#     "top_k": [
#         {"species": "Bengal tiger", "scientific_name": "Panthera tigris tigris", "confidence": 0.9954},
#         {"species": "dhole / Indian wild dog", "scientific_name": "Cuon alpinus", "confidence": 0.0039},
#         {"species": "Indian leopard", "scientific_name": "Panthera pardus fusca", "confidence": 0.0006}
#     ]
# }
```

---

## 6. Edge Case Handling

- **Invalid or None Crop**: Raises descriptive `ValueError`.
- **Empty or Under-sized Crop**: Rejects crops smaller than 5x5 pixels.
- **Grayscale / 1-Channel Images**: Automatically converted to 3-channel RGB.
- **Corrupted Inputs**: Checks for NaN/Inf values before tensor conversion.

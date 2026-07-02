# Vehicle Attribute Classifier

Multi-head classifier for vehicle type, make/model, and color.

## Architecture

EfficientNet or ConvNeXt-T backbone fine-tuned on a South-Asian vehicle dataset.

## Heads

- **Type**: 9-class (car, motorbike, scooter, auto_rickshaw, van, suv, truck, bus, other) — target ≥ 95% top-1
- **Make/model**: top-200 South-Asian models + "unknown" — target ≥ 80% top-5
- **Color**: 12 canonical colors — target ≥ 90% top-1

## Notes

Stanford Cars dataset is US-heavy; supplement with South-Asian collections covering
Bajaj, Hero, TVS, Mahindra, Tata, Maruti, Hyundai (Indian/Nepali variants).

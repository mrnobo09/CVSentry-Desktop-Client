# Known Faces Database

Place known face images here using the following structure:

```
faces/
├── John_Doe/
│   ├── front.jpg
│   ├── side.jpg
│   └── sunglasses.jpg
├── Jane_Smith/
│   ├── photo1.jpg
│   └── photo2.png
└── ...
```

## Rules
- **Folder name** = identity label (`John_Doe` → `"John Doe"`, underscores become spaces)
- **Supported formats**: `.jpg`, `.jpeg`, `.png`
- **Multiple images recommended** — all images per person are encoded and averaged into a single robust embedding. More variation (angles, lighting) = better recognition
- **Minimum**: 1 image per person (works but less accurate)

## After adding new faces
Either restart the face_detection service, or call the hot-reload endpoint:
```
POST http://localhost:8003/reload-faces
```

# Storyteller: "test with library images" button

A one-click way to test the slideshow pipeline without first generating
story-matching images -- click "Test bằng ảnh có sẵn (N)" next to the
slideshow image picker and it fills the ordered slide list with every image
currently in the asset library, in place of manually adding them one by one.
Frontend-only (`StorytellerPage.tsx`); no backend change, since the picker
already just builds `slide_asset_ids`.

# Brand Assets

VentWise keeps its product and repository artwork in two deliberately separate
locations.

## Home Assistant runtime assets

`custom_components/ventwise/brand/` is included in the integration package and
is used by Home Assistant 2026.3 and later for local custom-integration
branding.

- `icon.png` is the 256x256 PNG icon.
- `icon@2x.png` is the 512x512 high-density PNG icon.

The icon has a transparent background and is used as the logo fallback. Do not
add Home Assistant logos, badges, or certification claims to these files.

## Repository artwork

`docs/assets/brand/` contains the canonical high-resolution PNG exports used
by the repository, including the README banner and visual variants. This
artwork is not included in the Home Assistant integration package.

When changing the visual identity:

1. Update the high-resolution asset in `docs/assets/brand/`.
2. Export `icon.png` as a transparent 256x256 PNG and `icon@2x.png` as a
   transparent 512x512 PNG into `custom_components/ventwise/brand/`.
3. Check that the icon is recognizable at a small size on light and dark
   backgrounds.
4. Keep wording limited to implemented capabilities and describe VentWise as a
   Home Assistant custom integration.

For a future HACS/default submission, check the current publisher requirements
before opening the external pull request. HACS may require a corresponding
`home-assistant/brands` submission in addition to these local assets.

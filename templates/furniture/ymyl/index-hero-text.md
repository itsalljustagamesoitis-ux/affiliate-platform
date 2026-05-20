# YMYL index.astro hero text snippet

Replace the `home-intro__text` paragraph content in `index.astro` with:

```
Recommendations based on verified owner research, audiological sourcing, and hearing aid community consensus.
No sponsored content. No affiliate-influenced picks.
```

And update the `description` meta tag in the BaseLayout call from:
```
description={`Honest, tested reviews of ${cfg.site.niche} products. ${persona.bio_short}`}
```
to:
```
description={`Research-based guidance on ${cfg.site.niche} products. ${persona.bio_short}`}
```

This removes the "tested" claim from the meta description as well as the rendered page text.

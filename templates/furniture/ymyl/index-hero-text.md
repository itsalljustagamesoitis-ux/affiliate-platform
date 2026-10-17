# YMYL index.astro hero text snippet

Replace the `home-intro__text` paragraph content in `index.astro` with:

```
Buying guides are compiled from manufacturer specifications and current product listings. This site earns a commission on qualifying purchases made through links on this page. Guides are shopping research, not professional advice.
```

Do not claim owner research, community consensus, expert sourcing, "no sponsored content" or "no affiliate-influenced picks": the site does not test products and is paid when readers buy through its links.

And update the `description` meta tag in the BaseLayout call from:
```
description={`Honest, tested reviews of ${cfg.site.niche} products. ${persona.bio_short}`}
```
to:
```
description={`Research-based guidance on ${cfg.site.niche} products. ${persona.bio_short}`}
```

This removes the "tested" claim from the meta description as well as the rendered page text.

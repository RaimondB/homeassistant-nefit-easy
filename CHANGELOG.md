# Changelog

## [0.2.0](https://github.com/RaimondB/homeassistant-nefit-easy/compare/homeassistant-nefit-easy-v0.1.0...homeassistant-nefit-easy-v0.2.0) (2026-05-17)


### Features

* add app icon + refresh README status ([#25](https://github.com/RaimondB/homeassistant-nefit-easy/issues/25)) ([798d39e](https://github.com/RaimondB/homeassistant-nefit-easy/commit/798d39e4b8cda8d6df746beea69e5690335d2763))
* boiler status + problem from display code; drop block/lock/maint ([#19](https://github.com/RaimondB/homeassistant-nefit-easy/issues/19)) ([b1a69e0](https://github.com/RaimondB/homeassistant-nefit-easy/commit/b1a69e062950550e111406b074c8efc5f2456709))
* brands-compatible icon + logo assets ([#26](https://github.com/RaimondB/homeassistant-nefit-easy/issues/26)) ([cb0d1e9](https://github.com/RaimondB/homeassistant-nefit-easy/commit/cb0d1e978d4d3611407d526eb22d62fa867b1187))
* connection diagnostics + actionable error logging ([#11](https://github.com/RaimondB/homeassistant-nefit-easy/issues/11)) ([75c3147](https://github.com/RaimondB/homeassistant-nefit-easy/commit/75c3147ad5974809d2f70fbb5a7bfd0dc65f61ef))
* initial native Home Assistant Nefit/Bosch Easy integration ([9886432](https://github.com/RaimondB/homeassistant-nefit-easy/commit/9886432ac6938dbbe88464aa1d9f00311c13b80a))
* Phase 2 — switches, binary sensors, diagnostics ([#18](https://github.com/RaimondB/homeassistant-nefit-easy/issues/18)) ([44ea850](https://github.com/RaimondB/homeassistant-nefit-easy/commit/44ea850baafe2d545b77c3864ea228b5f7654929))
* Phase 3 — gas-usage history to HA long-term statistics ([#21](https://github.com/RaimondB/homeassistant-nefit-easy/issues/21)) ([4446014](https://github.com/RaimondB/homeassistant-nefit-easy/commit/44460146fed2ada94d51473a445ca30b53eac07b))
* separate program mode (manual/auto) from boiler indicator ([#16](https://github.com/RaimondB/homeassistant-nefit-easy/issues/16)) ([f32e62b](https://github.com/RaimondB/homeassistant-nefit-easy/commit/f32e62ba86ec658680364df84d024362ab7a7a85))


### Bug Fixes

* add debug logging to gas-usage import flow ([#23](https://github.com/RaimondB/homeassistant-nefit-easy/issues/23)) ([42cf153](https://github.com/RaimondB/homeassistant-nefit-easy/commit/42cf15377b24c4d67c9d3cc0ec7a60498359feac))
* add mean_type to StatisticMetaData for HA 2025+ compatibility ([#22](https://github.com/RaimondB/homeassistant-nefit-easy/issues/22)) ([044120e](https://github.com/RaimondB/homeassistant-nefit-easy/commit/044120e828d26299d2f1df0d9bf1658c4f4e6f71))
* align manifest slixmpp pin to 1.15.0 (matches requirements_test) ([9ea9bad](https://github.com/RaimondB/homeassistant-nefit-easy/commit/9ea9bade13adad6c23d5ae96ea1dbcaa632df652))
* bind slixmpp to HA's event loop (explicit loop injection) ([#13](https://github.com/RaimondB/homeassistant-nefit-easy/issues/13)) ([8f0cadf](https://github.com/RaimondB/homeassistant-nefit-easy/commit/8f0cadf8275f85eeafc03d8407d57b2be259998c))
* construct NefitClient off the event loop ([#10](https://github.com/RaimondB/homeassistant-nefit-easy/issues/10)) ([8f61f3d](https://github.com/RaimondB/homeassistant-nefit-easy/commit/8f61f3de6789a4774a8d39fad7dfe31a94b93c15))
* correct DeviceInfo import; add module import smoke test ([#9](https://github.com/RaimondB/homeassistant-nefit-easy/issues/9)) ([49ef746](https://github.com/RaimondB/homeassistant-nefit-easy/commit/49ef746c093ea74f49d781ead2d847083e1e14b5))
* **deps:** Bump slixmpp from 1.8.5 to 1.15.0 ([#4](https://github.com/RaimondB/homeassistant-nefit-easy/issues/4)) ([69ef624](https://github.com/RaimondB/homeassistant-nefit-easy/commit/69ef624876c938ca8e5695f6d9fd3b3547f2d0e4))
* force STARTTLS-only (slixmpp 1.15 direct-TLS regression) ([#14](https://github.com/RaimondB/homeassistant-nefit-easy/issues/14)) ([cd005ee](https://github.com/RaimondB/homeassistant-nefit-easy/commit/cd005eeccb0f14dc0b0c7fb894289995922ac0a6))
* gas import service works regardless of the config option ([#24](https://github.com/RaimondB/homeassistant-nefit-easy/issues/24)) ([af75f2b](https://github.com/RaimondB/homeassistant-nefit-easy/commit/af75f2bad02134dd9ec1c14f49e3980e2ef385d3))
* hassfest manifest key order and HACS validation ([40a641f](https://github.com/RaimondB/homeassistant-nefit-easy/commit/40a641f32585507be75db5bd580460542808a524))
* pin pytest-homeassistant-custom-component; drop cryptography pin ([#7](https://github.com/RaimondB/homeassistant-nefit-easy/issues/7)) ([c55413b](https://github.com/RaimondB/homeassistant-nefit-easy/commit/c55413baaef56aa58f4ab5134b3c17d7166ddcc0))
* working climate presets + cause_code-driven boiler_problem ([#20](https://github.com/RaimondB/homeassistant-nefit-easy/issues/20)) ([907ea63](https://github.com/RaimondB/homeassistant-nefit-easy/commit/907ea63b4ecea0f58ad1292bc61b36b341b2bc0b))
* working Nefit protocol client + standalone device probe ([#8](https://github.com/RaimondB/homeassistant-nefit-easy/issues/8)) ([a55d8b7](https://github.com/RaimondB/homeassistant-nefit-easy/commit/a55d8b750d2be6aadd932bea785f5a4a8a91ba7b))
* writes (PUT) — byte-identical bare stanza + set_temperature seq ([#15](https://github.com/RaimondB/homeassistant-nefit-easy/issues/15)) ([f994499](https://github.com/RaimondB/homeassistant-nefit-easy/commit/f9944999731c07ee016b6397178903ed4d39db5b))

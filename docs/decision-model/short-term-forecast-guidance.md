# Short-term forecast guidance

VentWise requests a near-term forecast from the weather entity selected during
setup. The forecast is used only after the current-condition decision has
selected `ventilate`: it bounds the proposed ventilation duration to a
conservative 15, 10, or 5 minutes.

It does not make a predictive `open` or `close` recommendation, reserve a
future opening window, or simulate multiple horizons. Current weather and
configured measurements remain the sole inputs to action selection.

The feature is automatic: no new source or setup step is required. If the
weather provider does not expose a usable forecast, VentWise retains the
current-condition decision and uses the conservative generic duration.

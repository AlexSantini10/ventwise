# Short-term forecast guidance

VentWise requests the hourly forecast from the weather entity selected during
setup. When the nearest upcoming forecast would make outdoor air materially
less comfortable, VentWise can give an early recommendation instead of waiting
until that change has already arrived.

For example, when a comfortable room is exposed to outdoor air that is forecast
to become much hotter or colder shortly, VentWise can recommend closing the
windows early. When outside air is helping an uncomfortable room now but will
soon become worse, it can recommend opening while the useful window remains.

The feature is automatic: no new source or setup step is required. Forecasts
are read at most every 15 minutes. If the weather provider does not expose an
hourly forecast, VentWise keeps using its existing current-condition model.

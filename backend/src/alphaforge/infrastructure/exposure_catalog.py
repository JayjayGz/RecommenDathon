"""Lire et dater le catalogue d’exposition fourni, sans le réécrire."""
import csv
from datetime import date
import hashlib
from io import StringIO
import re

from alphaforge.application.snapshots import DataUnavailable
from alphaforge.domain.exposures import parse_allocation

FIELDS = {"ticker", "asset_class", "description_fr", "repartition_sectorielle", "classification_sectorielle",
          "date_repartition_sectorielle", "repartition_geographique", "base_repartition_geographique",
          "date_repartition_geographique", "composition_classes_actifs", "base_composition_classes_actifs",
          "sources_repartitions", "limites_repartitions", "date_consultation"}


def parse_exposures(data, reference, as_of):
    try:
        reader = csv.DictReader(StringIO(data.decode("utf-8-sig")))
        if not FIELDS <= set(reader.fieldnames or []):
            raise ValueError("Colonnes du catalogue manquantes")
        result = {}
        for raw in reader:
            if any(raw.get(k) is None or len(raw[k]) > 6000 for k in FIELDS):
                raise ValueError("Champ du catalogue invalide")
            ticker = raw["ticker"]
            if ticker in result or not re.fullmatch(r"[A-Z0-9.^=-]{1,24}", ticker):
                raise ValueError("Identifiant du catalogue invalide ou répété")
            consulted = date.fromisoformat(raw["date_consultation"])
            row = {"ticker": ticker, "asset_class": raw["asset_class"],
                   "description_fr": raw["description_fr"] if consulted <= as_of else "",
                   "consulted_on": consulted.isoformat(), "sources": raw["sources_repartitions"],
                   "limitations": raw["limites_repartitions"]}
            for dimension, field, basis, dated in (
                ("sectors", "repartition_sectorielle", "classification_sectorielle", "date_repartition_sectorielle"),
                ("geography", "repartition_geographique", "base_repartition_geographique", "date_repartition_geographique"),
                ("asset_classes", "composition_classes_actifs", "base_composition_classes_actifs", "date_consultation")):
                allocation = parse_allocation(raw[field])
                observation = None
                if allocation is not None:
                    observation = date.fromisoformat(raw[dated])
                available = allocation is not None and consulted <= as_of and observation <= as_of
                row[dimension] = allocation if available else None
                row[dimension + "_basis"] = raw[basis]
                row[dimension + "_date"] = observation.isoformat() if observation else None
            result[ticker] = row
        if not result:
            raise ValueError("Catalogue vide")
        return result, {**reference, "sha256": hashlib.sha256(data).hexdigest(), "as_of": as_of.isoformat()}
    except (ValueError, TypeError, KeyError, UnicodeError, csv.Error) as error:
        raise DataUnavailable("INVALID_EXPOSURE_CATALOG") from error

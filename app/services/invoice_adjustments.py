"""Invoice adjustments, without interpreting the historically ambiguous tva field."""
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def invoice_rate(invoice):
    if invoice.taux_tva_snapshot is not None:
        return Decimal(str(invoice.taux_tva_snapshot))
    ht, ttc = money(invoice.total_ht), money(invoice.total_ttc)
    if ht == 0:
        if ttc == 0:
            return Decimal(0)
        raise HTTPException(status_code=409, detail="Taux de TVA indéterminable sur cette facture ; vérifiez ses montants.")
    rate = (ttc / ht - 1) * 100
    if rate < 0 or rate > 100:
        raise HTTPException(status_code=409, detail="Taux de TVA historique incohérent ; aucune modification appliquée.")
    return rate.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def invoice_totals(lines, discount, rate):
    subtotal = sum((money(line.total_ligne) for line in lines), Decimal(0))
    reduction = money(discount)
    if reduction < 0 or reduction > subtotal:
        raise HTTPException(status_code=422, detail="La remise doit être comprise entre zéro et le total HT des lignes.")
    net = subtotal - reduction
    tax = (net * rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return subtotal, net, tax, net + tax

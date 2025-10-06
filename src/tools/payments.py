# src/tools/payments.py
def make_upi_link(merchant_upi_id: str, amount: float, note: str = ""):
    note_enc = note.replace(" ", "%20")
    return f"upi://pay?pa={merchant_upi_id}&pn=Merchant&am={amount}&cu=INR&tn={note_enc}"

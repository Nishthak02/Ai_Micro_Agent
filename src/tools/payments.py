# src/tools/payments.py
def make_upi_link(merchant_upi_id: str, amount: float, note: str = ""):
    note_enc = note.replace(" ", "%20")

# def generate_upi_link(amount: float = 0, upi_id: str = "", note: str = "") -> str:
#     """
#     Generate a simple UPI payment link.
#     Example: generate_upi_link(100, "nishtha@upi", "Coffee Payment")
#     """
#     if not upi_id:
#         return "⚠️ UPI ID missing."

#     base_url = "upi://pay"
#     params = f"?pa={upi_id}&am={amount}&cu=INR&tn={note or 'Payment'}"
#     link = base_url + params
#     print(f"💰 Generated UPI link: {link}")
#     return link

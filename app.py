from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

app = Flask(__name__)

# ---------------------------
# FIREBASE INITIALIZATION
# ---------------------------
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------------------------
# GET ALL SERVICES
# ---------------------------
@app.route("/services", methods=["GET"])
def get_services():
    services = []
    docs = db.collection("services").stream()

    for doc in docs:
        data = doc.to_dict()
        data["service_id"] = doc.id
        services.append(data)

    return jsonify(services), 200


# ---------------------------
# GET AVAILABLE SLOTS BY SERVICE
# ---------------------------
@app.route("/slots/<service_id>", methods=["GET"])
def get_slots(service_id):
    slots = []
    docs = db.collection("slots") \
        .where("service_id", "==", service_id) \
        .where("is_booked", "==", False) \
        .stream()

    for doc in docs:
        data = doc.to_dict()
        data["slot_id"] = doc.id
        slots.append(data)

    return jsonify(slots), 200


# ---------------------------
# BOOK SLOT (NO DOUBLE BOOKING)
# ---------------------------
@app.route("/book", methods=["POST"])
def book_service():
    data = request.json

    user_name = data.get("name")
    service_id = data.get("service_id")
    slot_id = data.get("slot_id")

    if not user_name or not service_id or not slot_id:
        return jsonify({"error": "Missing required fields"}), 400

    slot_ref = db.collection("slots").document(slot_id)

    try:
        @firestore.transactional
        def book_transaction(transaction):
            slot_snapshot = slot_ref.get(transaction=transaction)

            if not slot_snapshot.exists:
                raise Exception("Slot not found")

            slot_data = slot_snapshot.to_dict()

            # ❌ Prevent double booking
            if slot_data.get("is_booked") is True:
                raise Exception("Slot already booked")

            # ✅ Mark slot as booked
            transaction.update(slot_ref, {
                "is_booked": True
            })

            # ✅ Create booking record
            booking_ref = db.collection("bookings").document()
            transaction.set(booking_ref, {
                "user_name": user_name,
                "service_id": service_id,
                "slot_id": slot_id,
                "start_time": slot_data.get("start_time"),
                "end_time": slot_data.get("end_time"),
                "status": "confirmed",
                "created_at": datetime.utcnow()
            })

            return booking_ref.id

        transaction = db.transaction()
        booking_id = book_transaction(transaction)

        return jsonify({
            "message": "Booking successful ✅",
            "booking_id": booking_id,
            "slot_id": slot_id
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------
# HEALTH CHECK (OPTIONAL)
# ---------------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Backend is running 🚀"}), 200


# ---------------------------
# RUN SERVER
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)

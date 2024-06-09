import streamlit as st
from collections import deque
import pymongo
import time
import datetime
import os

class MongoDB:
    def __init__(self):
        self.MyDatabase = st.secrets['MyDatabase']
        self.client = pymongo.MongoClient(f"mongodb+srv://{self.MyDatabase}.mongodb.net/")
        self.db = self.client["concert_database"]
        self.tickets = self.db["tickets"]
        self.users = self.db["users"]
        self.purchases = self.db["purchases"]
        self.concert_prices = self.db["concert_prices"]
        self.concert_capacity = self.db["concert_capacity"]

    def get_concert_prices(self):
        prices = {}
        for doc in self.concert_prices.find():
            prices[doc['concert']] = doc['prices']
        return prices

    def get_concert_capacity(self):
        capacity = {}
        for doc in self.concert_capacity.find():
            capacity[doc['concert']] = doc['capacity']
        return capacity

class Queue:
    def __init__(self):
        self.queue = deque()

    def enqueue(self, item):
        self.queue.append(item)

    def dequeue(self):
        if len(self.queue) != 0:
            return self.queue.popleft()
        else:
            return None

    def showQueue(self):
        if len(self.queue) != 0:
            return list(self.queue)
        else:
            return "Antrian Kosong"

    def nextQueue(self):
        if len(self.queue) != 0:
            return self.queue[0]
        else:
            return None

    def search_by_name(self, name):
        found_tickets = []
        for ticket in self.queue:
            if ticket['name'].lower() == name.lower():
                found_tickets.append(ticket)
        return found_tickets

    def remove_expired(self):
        current_time = time.time()
        while len(self.queue) > 0:
            if self.queue[0]['deadline'] < current_time:
                self.dequeue()
            else:
                break

class TicketPurchase:
    def __init__(self):
        self.db = MongoDB()
        self.priceKonser = self.db.get_concert_prices()
        self.capacityKonser = self.db.get_concert_capacity()

        if 'capacity' not in st.session_state:
            st.session_state['capacity'] = self.capacityKonser

        if 'payment_queue' not in st.session_state:
            st.session_state['payment_queue'] = Queue()
        self.payment_queue = st.session_state['payment_queue']

    def select_concert(self):
        concert = st.selectbox("Pilih konser", list(self.priceKonser.keys()))
        st.session_state['selected_concert'] = concert
        st.session_state['categories'] = self.priceKonser[concert]
        st.session_state['concert_selected'] = True

    def select_category(self):
        st.subheader("Kategori Tiket:")
        category = st.selectbox("Pilih kategori tiket", list(st.session_state['categories'].keys()))
        return category

    def generate_ticket_number(self):
        concert = st.session_state['selected_concert']
        category = st.session_state['selected_category']
        purchase_count = self.db.purchases.count_documents({"concert": concert, "category": category}) + 1
        ticket_number = f"{concert[:3].upper()}-{category[:3].upper()}-{purchase_count:04d}"
        return ticket_number

    def add_to_queue(self, name, ticket_number, category, quantity):
        total_price = st.session_state['categories'][category] * quantity
        deadline = time.time() + 300
        self.payment_queue.enqueue({
            'name': name,
            'ticket_number': ticket_number,
            'concert': st.session_state['selected_concert'],
            'category': category,
            'quantity': quantity,
            'total_price': total_price,
            'deadline': deadline
        })
        st.success(f"Tiket {category} sejumlah {quantity} berhasil ditambahkan ke antrian pembayaran.")
        st.write(f"Total harga: Rp {total_price}\n")
        st.session_state['category_selected'] = False
        st.session_state['total_price'] = 0
        st.session_state['concert_selected'] = False

    def process_payments(self):
        self.payment_queue.remove_expired()
        if self.payment_queue.nextQueue() is None:
            st.warning("Tidak ada antrian pembayaran.\n")
        else:
            transaction = self.payment_queue.nextQueue()
            if transaction:
                name = transaction['name']
                ticket_number = transaction['ticket_number']
                category = transaction['category']
                quantity = transaction['quantity']
                total_price = transaction['total_price']
                deadline = transaction['deadline']

                st.text(
                    f"Memproses pembayaran tiket {category} sejumlah {quantity} untuk {name} (No. Tiket: {ticket_number})")
                st.write(f"Total harga yang harus dibayar: Rp {total_price}")

                remaining_time = deadline - time.time()
                minutes, seconds = divmod(remaining_time, 60)
                st.write(f"Waktu tersisa: {int(minutes)} menit {int(seconds)} detik")

                payment = st.number_input("Masukkan jumlah pembayaran", min_value=0, step=1)

                if st.button("Lakukan Pembayaran", key="pay_button"):
                    if payment >= total_price:
                        change = payment - total_price
                        self.payment_queue.dequeue()
                        concert = transaction['concert']
                        st.session_state['capacity'][concert][category] -= quantity

                        self.db.concert_capacity.update_one(
                            {"concert": concert},
                            {"$inc": {f"capacity.{category}": -quantity}}
                        )

                        self.db.purchases.insert_one({
                            "name": name,
                            "ticket_number": ticket_number,
                            "concert": concert,
                            "category": category,
                            "quantity": quantity,
                            "total_price": total_price,
                            "purchase_time": datetime.datetime.now()
                        })

                        st.success("Pembayaran berhasil.\n")
                        st.write(f"Kembalian Anda: Rp {change}")
                        st.write(f"Tiket {category} sejumlah {quantity} untuk {name} telah terbayar.")
                        st.write(f"No. Tiket: {ticket_number}")
                        time.sleep(5)
                        st.rerun()
                    else:
                        st.warning("Jumlah pembayaran tidak mencukupi.\n")
            else:
                st.warning("Tidak ada antrian pembayaran untuk pengguna saat ini.\n")

def main_menu():
    if 'page' not in st.session_state:
        st.session_state.page = "Lihat List Konser"

    st.sidebar.title("Menu")
    if st.sidebar.button("Lihat List Konser", key="lihat_list_konser_button"):
        st.session_state.page = "Lihat List Konser"
        st.rerun()
    if st.sidebar.button("Pembelian Tiket", key="pembelian_tiket_button"):
        st.session_state.page = "Pembelian Tiket"
        st.rerun()
    if st.sidebar.button("Proses Pembayaran", key="proses_pembayaran_button"):
        st.session_state.page = "Proses Pembayaran"
        st.rerun()
    if st.sidebar.button("Lacak Antrian Tiket", key="lacak_tiket_button"):
        st.session_state.page = "Lacak Antrian Tiket"
        st.rerun()

    if st.session_state.page == "Lihat List Konser":
        st.header("List Konser")

        purchase_system = TicketPurchase()
        price_dict = purchase_system.priceKonser
        capacity_dict = st.session_state['capacity']
        max_cap = ['500', '1000', '2000', '5000']
        for concert, categories in capacity_dict.items():
            with st.container():
                st.write(f"### {concert}")
                for i, (category, capacity) in enumerate(categories.items()):
                    price = price_dict[concert][category]
                    st.write(f"- {category}: Rp {price} (Kapasitas tersedia: "
                             f"{capacity}/{max_cap[i % len(max_cap)]})")
                st.write("---")

    elif st.session_state.page == "Pembelian Tiket":
        st.header("Beli Tiket")
        purchase_system = TicketPurchase()
        purchase_system.select_concert()
        if st.session_state.get('concert_selected', False):
            name = st.text_input("Masukkan nama Anda")
            st.session_state['selected_category'] = purchase_system.select_category()
            ticket_number = purchase_system.generate_ticket_number()
            quantity = 1
            st.session_state['total_price'] = st.session_state['categories'][
                                                  st.session_state['selected_category']] * quantity
            st.write(f"Total harga: Rp {st.session_state['total_price']}")
            if st.button("Buy Now", key="buy_now_button"):
                purchase_system.add_to_queue(name, ticket_number, st.session_state['selected_category'], quantity)
                st.session_state.page = "Lihat List Konser"
                st.rerun()

    elif st.session_state.page == "Proses Pembayaran":
        st.header("Proses Pembayaran")
        purchase_system = TicketPurchase()
        purchase_system.process_payments()
        if st.button("Kembali ke Halaman Utama", key="back_home_button"):
            st.session_state.page = "Lihat List Konser"
            st.rerun()

    elif st.session_state.page == "Lacak Antrian Tiket":
        st.header("Lacak Antrian Tiket")
        name_to_search = st.text_input("Cari berdasarkan nama")
        if st.button("Cari", key="search_button"):
            payment_queue = st.session_state['payment_queue']
            found_tickets = payment_queue.search_by_name(name_to_search)
            if found_tickets:
                for ticket in found_tickets:
                    st.write(
                        f"Nama: {ticket['name']}, Nomor Tiket: {ticket['ticket_number']}, Konser: {ticket['concert']}, Kategori: {ticket['category']}, Jumlah: {ticket['quantity']}, Total Harga: Rp {ticket['total_price']}")
            else:
                st.write("Tidak ada tiket yang ditemukan untuk nama tersebut.")

        if st.button("Tampilkan Semua Antrian", key="show_queue_button"):
            payment_queue = st.session_state['payment_queue']
            all_tickets = payment_queue.showQueue()
            if all_tickets != "Antrian Kosong":
                col1, col2, col3, col4, col5, col6 = st.columns([7,11,12,5,5,6])
                col1.write("Nama")
                col2.write("Nomor Tiket")
                col3.write("Konser")
                col4.write("Kategori")
                col5.write("Jumlah")
                col6.write("Total Harga")

                for ticket in all_tickets:
                    col1.write(ticket['name'])
                    col2.write(ticket['ticket_number'])
                    col3.write(ticket['concert'])
                    col4.write(ticket['category'])
                    col5.write(ticket['quantity'])
                    col6.write(ticket['total_price'])
            else:
                st.write(all_tickets)

if __name__ == "__main__":
    main_menu()

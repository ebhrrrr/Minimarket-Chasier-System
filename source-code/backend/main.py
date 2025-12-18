import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
from datetime import datetime
import csv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'cashier.db')
RECEIPT_DIR = os.path.join(BASE_DIR, 'receipts')

os.makedirs(RECEIPT_DIR, exist_ok=True)

def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            stock INTEGER NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            total INTEGER NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            product_id INTEGER,
            qty INTEGER,
            subtotal INTEGER,
            FOREIGN KEY(sale_id) REFERENCES sales(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    ''')
    conn.commit()
    conn.close()

def seed_sample_products():
    conn = get_db_conn()
    cur = conn.cursor()
    sample = [
        ('E026', 'Mizone', 3000, 20),
        ('E027', 'Bubble Gum', 4000, 15),
        ('E028', 'Sunpride Banana', 5000, 10),
        ('B051', 'Crackers', 12000, 30),
        ('C076', 'Ketchup', 12000, 25),
    ]
    for sku, name, price, stock in sample:
        try:
            cur.execute('INSERT INTO products (sku,name,price,stock) VALUES (?,?,?,?)',
                        (sku, name, price, stock))
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()

class Product:
    def __init__(self, row):
        self.id = row['id']
        self.sku = row['sku']
        self.name = row['name']
        self.price = row['price']
        self.stock = row['stock']

class CartItem:
    def __init__(self, product: Product, qty: int):
        self.product = product
        self.qty = qty

    @property
    def subtotal(self):
        return self.qty * self.product.price

def auto_adjust_treeview(tree):
    tree.update_idletasks()
    for col in tree["columns"]:
        max_width = tkfont.Font().measure(col) + 20
        for item in tree.get_children():
            cell_text = tree.set(item, col)
            cell_width = tkfont.Font().measure(cell_text) + 20
            if cell_width > max_width:
                max_width = cell_width
        tree.column(col, width=max_width)

class CashierApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Kasir Minimarket')
        self.geometry('1000x700')
        self.resizable(False, False)
        self.config(bg="#FFE7FC")
        self.conn = get_db_conn()

        self.left_frame = tk.Frame(self, bg="#FCB7F2", bd=2, relief='groove')
        self.left_frame.place(x=20, y=20, width=600, height=660)

        self.right_frame = tk.Frame(self, bg="#FCBBF6", bd=2, relief='groove')
        self.right_frame.place(x=640, y=20, width=340, height=660)

        self.search_var = tk.StringVar()
        tk.Label(self.left_frame, text='Search Product:', bg="#f9d6f1").pack(anchor='nw', padx=10, pady=(8, 0))
        sframe = tk.Frame(self.left_frame, bg="#ffe0f8")
        sframe.pack(fill='x', padx=10)
        tk.Entry(sframe, textvariable=self.search_var).pack(side='left', fill='x', expand=True)
        tk.Button(sframe, text='Search', command=self.load_products).pack(side='left', padx=6)
        tk.Button(sframe, text='Refresh', command=self.load_products).pack(side='left', padx=6)

        cols = ('id', 'sku', 'name', 'price', 'stock')
        self.tree = ttk.Treeview(self.left_frame, columns=cols, show='headings', height=20)
        for c in cols:
            self.tree.heading(c, text=c.title())
        self.tree.column('id', width=40)
        self.tree.column('sku', width=100)
        self.tree.column('name', width=220)
        self.tree.column('price', width=80)
        self.tree.column('stock', width=60)
        self.tree.pack(padx=10, pady=8, fill='both', expand=True)
        self.tree.bind('<Double-1>', self.on_product_double_click)

        ctl = tk.Frame(self.left_frame, bg="#ffb5ff")
        ctl.pack(fill='x', padx=10, pady=6)
        tk.Button(ctl, text='Add Product', command=self.open_add_product).pack(side='left')
        tk.Button(ctl, text='Edit Product', command=self.open_edit_product).pack(side='left', padx=6)
        tk.Button(ctl, text='Delete Product', command=self.delete_selected_product).pack(side='left', padx=6)
        tk.Button(ctl, text='Import CSV', command=self.import_products_csv).pack(side='left', padx=6)

        cart_top = tk.Frame(self.right_frame, bg="#fadef3")
        cart_top.pack(fill='both', expand=False, padx=4, pady=(6, 0))

        tk.Label(cart_top, text='Cart', bg="#fadef3", font=('Arial', 12, 'bold')).pack(pady=6)
        self.cart_box = ttk.Treeview(
            cart_top,
            columns=('sku', 'name', 'qty', 'price', 'subtotal'),
            show='headings',
            height=9
        )
        for c in ('sku', 'name', 'qty', 'price', 'subtotal'):
            self.cart_box.heading(c, text=c.title())
        self.cart_box.column('sku', width=80)
        self.cart_box.column('name', width=120)
        self.cart_box.column('qty', width=50)
        self.cart_box.column('price', width=80)
        self.cart_box.column('subtotal', width=100)
        self.cart_box.pack(padx=8, pady=6, fill='both')

        btns = tk.Frame(cart_top, bg="#f8b4e3")
        btns.pack(fill='x', padx=8)
        tk.Button(btns, text='Delete Item', command=self.remove_cart_item).pack(side='left', padx=4)
        tk.Button(btns, text='Update Qty', command=self.update_cart_qty).pack(side='left', padx=4)
        tk.Button(btns, text='Clear Cart', command=self.clear_cart).pack(side='left', padx=4)

        self.var_sub = tk.IntVar(value=0)
        self.var_tax = tk.DoubleVar(value=11.0)
        self.var_total = tk.IntVar(value=0)

        sum_frame = tk.Frame(cart_top, bg="#ffc5f4")
        sum_frame.pack(fill='x', padx=8, pady=6)
        tk.Label(sum_frame, text='Subtotal:', bg='#ffc5f4').grid(row=0, column=0, sticky='w')
        tk.Label(sum_frame, textvariable=self.var_sub, bg='#ffc5f4').grid(row=0, column=1, sticky='e')

        tk.Label(sum_frame, text='Tax %:', bg='#ffc5f4').grid(row=1, column=0, sticky='w')
        tk.Entry(sum_frame, textvariable=self.var_tax, width=6).grid(row=1, column=1, sticky='e')

        tk.Label(sum_frame, text='Total:', bg='#ffc5f4', font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=(6, 0))
        tk.Label(sum_frame, textvariable=self.var_total, bg='#ffc5f4', font=('Arial', 10, 'bold')).grid(row=2, column=1, sticky='e', pady=(6, 0))

        tk.Button(cart_top, text='The Grand Total', bg="#FFE6FD", fg='black', command=self.calculate_total).pack(fill='x', padx=8, pady=6)
        tk.Button(cart_top, text='Checkout', bg='#FFE6FD', fg='black', command=self.checkout).pack(fill='x', padx=8, pady=(0,6))

        receipt_frame = tk.Frame(self.right_frame, bg="#f6d9f2", bd=1, relief='sunken')
        receipt_frame.pack(fill='both', expand=True, padx=8, pady=(6, 8))

        tk.Label(receipt_frame, text='Preview Receipt', bg="#f6d9f2", font=('Arial', 11, 'bold')).pack(anchor='nw', padx=6, pady=(6, 0))

        txt_frame = tk.Frame(receipt_frame)
        txt_frame.pack(fill='both', expand=True, padx=6, pady=6)

        self.receipt_text = tk.Text(txt_frame, wrap='none', state='disabled', height=12, font=('Courier', 10))
        self.receipt_text.pack(side='left', fill='both', expand=True)

        vsb = ttk.Scrollbar(txt_frame, orient='vertical', command=self.receipt_text.yview)
        vsb.pack(side='right', fill='y')
        self.receipt_text['yscrollcommand'] = vsb.set

        self.cart = []
        self.load_products()

    def load_products(self):
        q = self.search_var.get().strip()
        cur = self.conn.cursor()
        if q:
            cur.execute("SELECT * FROM products WHERE sku LIKE ? OR name LIKE ?", (f'%{q}%', f'%{q}%'))
        else:
            cur.execute("SELECT * FROM products ORDER BY name")
        rows = cur.fetchall()
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert('', 'end', values=(r["id"], r["sku"], r["name"], r["price"], r["stock"]))

    def on_product_double_click(self, event):
        sel = self.tree.focus()
        if not sel: return
        vals = self.tree.item(sel)['values']
        pid = vals[0]
        r = self.conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        prod = Product(r)

        qty = simple_qty_dialog(self, f"Enter The Amount {prod.name} (stock {prod.stock}):")
        if qty is None: return
        if qty > prod.stock:
            messagebox.showwarning("Stock", "Overstock!")
            return

        self.add_to_cart(prod, qty)

    def add_to_cart(self, prod, qty):
        for it in self.cart:
            if it.product.id == prod.id:
                it.qty += qty
                self.refresh_cart_view()
                return
        self.cart.append(CartItem(prod, qty))
        self.refresh_cart_view()

    def refresh_cart_view(self):
        self.cart_box.delete(*self.cart_box.get_children())
        sub = 0
        for it in self.cart:
            self.cart_box.insert('', 'end', values=(it.product.sku, it.product.name,
                                                    it.qty, it.product.price, it.subtotal))
            sub += it.subtotal
        self.var_sub.set(sub)
        self.calculate_total(update_only=True)
        auto_adjust_treeview(self.cart_box)

    def remove_cart_item(self):
        sel = self.cart_box.focus()
        if not sel:
            messagebox.showinfo("Info", "Select item to delete.")
            return
        sku = self.cart_box.item(sel)['values'][0]
        self.cart = [it for it in self.cart if it.product.sku != sku]
        self.refresh_cart_view()

    def update_cart_qty(self):
        sel = self.cart_box.focus()
        if not sel:
            messagebox.showinfo("Info", "Select item.")
            return
        sku = self.cart_box.item(sel)['values'][0]
        current = next((it for it in self.cart if it.product.sku == sku), None)

        qty = simple_qty_dialog(self, f"Add new product for {current.product.name}:", default=current.qty)
        if qty is None: return
        if qty <= 0:
            self.cart = [it for it in self.cart if it.product.sku != sku]
        else:
            current.qty = qty
        self.refresh_cart_view()

    def clear_cart(self):
        if self.cart and messagebox.askyesno("Confirm", "Clear the cart?"):
            self.cart.clear()
            self.refresh_cart_view()

    def open_add_product(self):
        ProductDialog(self, mode='add').wait_window()
        self.load_products()

    def open_edit_product(self):
        sel = self.tree.focus()
        if not sel:
            messagebox.showwarning("Info", "Choose a product first!")
            return
        pid = self.tree.item(sel)['values'][0]
        ProductDialog(self, mode='edit', product_id=pid).wait_window()
        self.load_products()

    def delete_selected_product(self):
        sel = self.tree.focus()
        if not sel:
            messagebox.showwarning("Info", "Select product to delete!")
            return
        pid = self.tree.item(sel)['values'][0]
        if not messagebox.askyesno("Confirm", "Are you sure you want to delete the product?"):
            return
        self.conn.execute("DELETE FROM products WHERE id=?", (pid,))
        self.conn.commit()
        self.load_products()

    def import_products_csv(self):
        path = filedialog.askopenfilename(filetypes=[('CSV Files', '*.csv')])
        if not path: return
        imported = 0
        with open(path, newline='', encoding='utf-8') as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                sku = row.get('sku')
                name = row.get('name')
                price = int(row.get('price', 0))
                stock = int(row.get('stock', 0))
                try:
                    self.conn.execute(
                        "INSERT INTO products (sku, name, price, stock) VALUES (?,?,?,?)",
                        (sku, name, price, stock)
                    )
                    imported += 1
                except sqlite3.IntegrityError:
                    pass
        self.conn.commit()
        messagebox.showinfo("Import", f"Imported successfully {imported} product.")
        self.load_products()

    def calculate_total(self, update_only=False):
        sub = self.var_sub.get()
        try:
            tax = float(self.var_tax.get())
        except:
            tax = 0.0
            self.var_tax.set(0.0)
        total = sub + int(sub * tax / 100)
        self.var_total.set(total)

        if not update_only:
            messagebox.showinfo("Total", f"Subtotal: Rp{sub:,}\nTotal: Rp{total:,}")

    def generate_receipt_text(self, sale_time, total, cart_items):
        lines = []
        lines.append("      === RECEIPT ===")
        lines.append("")
        lines.append(f"Time: {sale_time}")
        lines.append("-" * 26)
        lines.append(f"{'Item':15} {'Qty':>3} {'Subtotal':>9}")
        lines.append("-" * 26)
        for it in cart_items:
            name = it.product.name
            name_display = name[:12] + "..." if len(name) > 15 else name.ljust(15)
            qty = str(it.qty).rjust(3)
            subtotal = f"Rp{it.subtotal:,}".rjust(9)
            lines.append(f"{name_display} {qty} {subtotal}")
        lines.append("-" * 26)
        lines.append(f"{'TOTAL':>20} {f'Rp{total:,}':>9}")
        lines.append("")
        lines.append("Thank you for your purchase!")
        return "\n".join(lines)

    def render_receipt_to_gui(self, receipt_text):
        self.receipt_text.config(state='normal')
        self.receipt_text.delete('1.0', tk.END)
        self.receipt_text.insert(tk.END, receipt_text)
        self.receipt_text.config(state='disabled')

    def checkout(self):
        if not self.cart:
            messagebox.showwarning("Empty", "Cart is empty.")
            return

        self.calculate_total(update_only=True)
        total = self.var_total.get()

        if not messagebox.askyesno("Checkout", f"Total: Rp{total:,}\nContinue?"):
            return

        cur = self.conn.cursor()
        now = datetime.now().isoformat(' ', 'seconds')
        cur.execute("INSERT INTO sales (datetime, total) VALUES (?,?)", (now, total))
        sale_id = cur.lastrowid

        for it in self.cart:
            cur.execute(
                "INSERT INTO sale_items (sale_id, product_id, qty, subtotal) VALUES (?,?,?,?)",
                (sale_id, it.product.id, it.qty, it.subtotal)
            )
            cur.execute("UPDATE products SET stock = stock - ? WHERE id=?", (it.qty, it.product.id))

        self.conn.commit()

        receipt_text = self.generate_receipt_text(now, total, list(self.cart))

        fname = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        fpath = os.path.join(RECEIPT_DIR, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(receipt_text + "\n")

        self.render_receipt_to_gui(receipt_text)

        messagebox.showinfo("Success", f"Checkout was successful!\nReceipt saved in:\n{fpath}")

        self.cart.clear()
        self.refresh_cart_view()
        self.load_products()

def simple_qty_dialog(parent, prompt, default=1):
    d = tk.Toplevel(parent)
    d.title("Total")
    d.geometry("300x140")
    v = tk.StringVar(value=str(default))

    tk.Label(d, text=prompt, wraplength=260).pack(pady=6)
    e = tk.Entry(d, textvariable=v, justify='center')
    e.pack()

    out = {'qty': None}

    def ok():
        try:
            out['qty'] = int(v.get())
            d.destroy()
        except:
            messagebox.showerror("Error", "Enter a valid number.")

    tk.Button(d, text='OK', command=ok).pack(pady=8)
    d.transient(parent)
    d.grab_set()
    parent.wait_window(d)
    return out['qty']

class ProductDialog(tk.Toplevel):
    def __init__(self, parent, mode='add', product_id=None):
        super().__init__(parent)
        self.parent = parent
        self.mode = mode
        self.product_id = product_id
        self.title('Add Product' if mode == 'add' else 'Edit Product')
        self.geometry('360x200')

        tk.Label(self, text='SKU:').place(x=10, y=12)
        tk.Label(self, text='Name:').place(x=10, y=42)
        tk.Label(self, text='Price:').place(x=10, y=72)
        tk.Label(self, text='Stock:').place(x=10, y=102)

        self.sku_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.price_var = tk.StringVar()
        self.stock_var = tk.StringVar(value='0')

        tk.Entry(self, textvariable=self.sku_var).place(x=90, y=12, width=240)
        tk.Entry(self, textvariable=self.name_var).place(x=90, y=42, width=240)
        tk.Entry(self, textvariable=self.price_var).place(x=90, y=72, width=240)
        tk.Entry(self, textvariable=self.stock_var).place(x=90, y=102, width=240)

        tk.Button(self, text='Save', command=self.save).place(x=130, y=150)

        if mode == 'edit' and product_id:
            r = self.parent.conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
            if r:
                self.sku_var.set(r['sku'])
                self.name_var.set(r['name'])
                self.price_var.set(str(r['price']))
                self.stock_var.set(str(r['stock']))

    def save(self):
        sku = self.sku_var.get().strip()
        name = self.name_var.get().strip()
        try:
            price = int(self.price_var.get())
            stock = int(self.stock_var.get())
        except:
            messagebox.showerror("Error", "Price and stock must be numbers.")
            return
        if not sku or not name:
            messagebox.showerror("Error", "All field must be filled in.")
            return

        cur = self.parent.conn.cursor()
        if self.mode == 'add':
            try:
                cur.execute("INSERT INTO products (sku,name,price,stock) VALUES (?,?,?,?)",
                            (sku, name, price, stock))
                self.parent.conn.commit()
                messagebox.showinfo("OK", "The product has been successfully saved.")
                self.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "SKU already used.")
        else:
            cur.execute("UPDATE products SET sku=?,name=?,price=?,stock=? WHERE id=?",
                        (sku, name, price, stock, self.product_id))
            self.parent.conn.commit()
            messagebox.showinfo("OK", "The product has been successfully updated.")
            self.destroy()

def create_opening_window_and_start():
    opener = tk.Tk()
    opener.title("Welcome - Fun Mart")
    opener.geometry("520x300")
    opener.resizable(False, False)

    main_frame = tk.Frame(opener, bg="#FFF0F7")
    main_frame.pack(fill='both', expand=True)

    title_lbl = tk.Label(main_frame, text="Welcome to Fun Mart", font=('Helvetica', 26, 'bold'), bg="#FFF0F7")
    title_lbl.pack(pady=(24, 6))

    subtitle_lbl = tk.Label(main_frame, text="Minimarket Cashier System", font=('Helvetica', 12), bg="#FFF0F7")
    subtitle_lbl.pack(pady=(0, 18))

    btns_frame = tk.Frame(main_frame, bg="#FFF0F7")
    btns_frame.pack(pady=(4, 10))

    def start_app():
        opener.destroy()
        app = CashierApp()
        app.mainloop()

    start_btn = tk.Button(btns_frame, text="Start", font=('Helvetica', 14), width=12, command=start_app)
    start_btn.grid(row=0, column=0, pady=(0,6))

    tutorial_btn = tk.Button(btns_frame, text="Tutorial", font=('Helvetica', 12), width=16)
    tutorial_btn.grid(row=1, column=0)

    opener.bind('<Return>', lambda e: start_app())

    tutorial_frame = tk.Frame(opener, bg="#FFF7FB")

    tutorial_title = tk.Label(tutorial_frame, text="Tutorial", font=('Helvetica', 18, 'bold'), bg="#FFF7FB")
    tutorial_title.pack(pady=(12, 6))

    tutorial_text = tk.Text(tutorial_frame, wrap='word', height=10, width=60, padx=10, pady=10)
    tutorial_text.insert('1.0', (
        "How to use the application:\n"
        "1. Click 'Start' to enter the application.\n"
        "2. Seaarch products through the search field.\n"
        "3. Double-click product to add to cart, then enter the quantity.\n"
        "4. Manage the contents of the cart (Update/Delete/Clear).\n"
        "5. Click 'Grand Total' to see the subtotal(Price before tax) and total(Price after tax).\n"
        "6. Click 'Checkout' to save the transaction and print the receipt.\n"
        "7. The receipt will appear in the receipt preview area at the bottom right.\n"
        "8. Enjoy using the minimarket cashier application!\n"
    ))
    tutorial_text.config(state='disabled')
    tutorial_text.pack(padx=12, pady=(0,8))

    def back_to_main():
        tutorial_frame.pack_forget()
        main_frame.pack(fill='both', expand=True)

    back_btn = tk.Button(tutorial_frame, text="Back", font=('Helvetica', 12), width=12, command=back_to_main)
    back_btn.pack(pady=(0, 12))

    def open_tutorial():
        main_frame.pack_forget()
        tutorial_frame.pack(fill='both', expand=True)

    tutorial_btn.config(command=open_tutorial)

    opener.mainloop()

def main():
    init_db()
    seed_sample_products()
    create_opening_window_and_start()

if __name__ == '__main__':
    main()

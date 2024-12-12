import streamlit as st
import json
import sqlite3
import os
from PIL import Image
import torch
from datetime import datetime
import holidays
import numpy as np
from keras.models import load_model
import google.generativeai as genai
from dotenv import load_dotenv
import warnings
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from io import BytesIO

warnings.filterwarnings("ignore")

# Configure Generative AI with the new API key
api_key = "AIzaSyD6ZxfgXOo3rr5NAyCDm7bsdWv8Q8U4T9U"
genai.configure(api_key=api_key)

# Load the model
price_model = load_model(r"C:\Users\RACHANA KULKARNI\Downloads\ServeSmart-main\ServeSmart-main\User Interface\model.h5")

# Holiday check
holidays = holidays.Turkey()
is_holiday = 1 if datetime.now().date() in holidays else 0

# Hour-based sin/cos features
hour = datetime.now().hour
sin = np.sin(2 * np.pi * hour / 24)
cos = np.cos(2 * np.pi * hour / 24)

# Predict discount based on price
prediction = price_model.predict(np.array([[sin, cos, is_holiday]]))

discount = 0
if prediction > 2500:
    discount = 20
elif prediction > 2000:
    discount = 10
elif prediction > 1500:
    discount = 5

# Ensure image directory exists
os.makedirs("product_images", exist_ok=True)

# Database setup
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_no TEXT NOT NULL CHECK(length(identity_no) = 11 AND identity_no GLOB '[0-9]*'),
    CVV TEXT NOT NULL,
    card_no TEXT NOT NULL,
    address TEXT NOT NULL,
    e_mail TEXT NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sellers (
    seller_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL UNIQUE,            
    identity_no TEXT NOT NULL UNIQUE CHECK(length(identity_no) = 11 AND identity_no GLOB '[0-9]*'),
    IBAN TEXT NOT NULL,
    business_address TEXT NOT NULL,
    e_mail TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER,
    product_name TEXT NOT NULL,
    description TEXT,
    purchase_count INTEGER DEFAULT 0,
    product_image_path TEXT,
    price REAL NOT NULL,
    discount REAL NOT NULL,
    FOREIGN KEY (seller_id) REFERENCES sellers (seller_id)
);
""")

conn.commit()
conn.close()

st.set_page_config(
    page_title="ServeSmart",
    layout="centered",
    initial_sidebar_state="expanded",
    page_icon="🍽"
)

with st.sidebar:
    st.title("Navigation")
    choice = st.radio("Menu", ["Create Account to Sell", "Sell Product", "Search Product", "Buy Product", "See or Delete Your Products", "Sales Analysis"])

if choice == "Create Account to Sell":
    st.title("Welcome to ServeSmart :wave: Create an Account and Help Prevent Waste")
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    with st.form("create_an_account"):
        s_username = st.text_input("Username: ", max_chars=20)
        s_password = st.text_input("Password: ", max_chars=20, type="password")
        iban = st.text_input("Your IBAN to payment: ")
        s_i_no = st.text_input("Your identity number: ", max_chars=11)
        s_e_mail = st.text_input("Your E-Mail address: ")
        business_address = st.text_input("Your business address:")
        create_account = st.form_submit_button("Create an Account")

        if create_account:
            if s_i_no and len(s_i_no) == 11 and s_i_no.isdigit():
                try:
                    cursor.execute("""
                        INSERT INTO sellers (user_name, identity_no, IBAN, business_address, e_mail, password)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (s_username, s_i_no, iban, business_address, s_e_mail, s_password))
                    
                    conn.commit() 
                    st.success("Account created successfully!")
                    
                except sqlite3.IntegrityError:
                    st.error("An account with this identity number or email already exists.")
                
            else:
                st.error("Please enter a valid 11-digit identity number consisting of numbers only.")

elif choice == "Sell Product":
    st.title("Welcome to ServeSmart :wave: Sell Your Products and Help Prevent Waste")

    with st.form("add_product_form"):
        st.write("Provide a short explanation of your product, and our AI will generate a title and description upon submission. You can also upload a product photo.")
    
        username = st.text_input("Your username: ")
        password = st.text_input("Your Password: ", type="password")
        exp = st.text_area("Please write a short explanation")
        img = st.camera_input("Photo of your product:")
        price = st.number_input("Price of your product:", min_value=0.0)
        st.write("Attention please! Price may change on our AI model.")
        submit_product_button = st.form_submit_button("Submit Product")

        if submit_product_button:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT seller_id FROM sellers WHERE user_name = ? AND password = ?", (username, password))
            seller = cursor.fetchone()

            if seller:
                seller_id = seller[0]
                price = price - discount  
                
                # AI Model to generate product title and description
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = f"""
                You are extracting a food title and description from the given text, rewriting and enhancing the description when necessary.
                Always respond in the user's input language.
                Always answer in the given plain text format. Do not use any other keywords. Do not make up any information.
                The description must contain at least 5 sentences.
                Now answer this:
                Food Information: {exp}
                """

                response = model.generate_content(prompt)

                # Display the raw response text
                st.write("Raw Response:")
                st.write(response.text)  # Displaying raw response as plain text
                
                # Image processing and saving the product
                img = Image.open(img)
                image_path = f"product_images/{exp.replace(' ', '')}.jpg"
                img.save(image_path)

                cursor.execute("INSERT INTO products (seller_id, product_name, description, price, product_image_path, discount) VALUES (?, ?, ?, ?, ?, ?)",
                               (seller_id, response.text.split("\n")[0], response.text.split("\n")[1], price, image_path, discount))
                conn.commit()
                conn.close()

                st.success("Product submitted successfully.")
            else:
                st.warning("Username and password do not match. Please try again.")

elif choice == "Search Product":
    with st.form("customer_searching_form"):
        st.title("Find a Product and Buy from Other Page")
        st.write("Attention please: You will need product ID to buy.")
        search_query = st.text_input("Search for a product by name:")
        search_button = st.form_submit_button("Search")

        if search_button:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE product_name LIKE ?", ('%' + search_query + '%',))
            products = cursor.fetchall()

            if products:
                product_names = []
                purchase_counts = []

                for product in products:
                    product_id, seller_id, product_name, description, purchase_count, product_image_path, price, discount = product
                    st.write(f"Product ID: {product_id}")
                    st.write(f"Product Name: {product_name}")
                    st.write(f"Description: {description}")
                    st.write(f"Price: ${price}")
                    st.write(f"Discount: ${discount}")
                    st.write(f"Purchased: {purchase_count} times")

                    if product_image_path and os.path.exists(product_image_path):
                        img = Image.open(product_image_path)
                        st.image(img, caption=product_name)

                    product_names.append(product_name)
                    purchase_counts.append(purchase_count)

                df = pd.DataFrame({
                    "Product Name": product_names,
                    "Purchase Count": purchase_counts
                })

                st.subheader("Sales Summary")
                fig = px.bar(df, x="Product Name", y="Purchase Count", title="Popularity of Searched Products")
                st.plotly_chart(fig)

            else:
                st.warning("No products found.")

elif choice == "Buy Product":
    st.title("Hello there :wave: Here you can buy a product.")

    with st.form("customer_buying_form"):
        st.title("Find a Product from Other Page and Buy Here")
        st.write("Attention please: You will need product ID to buy.")
        p_id=st.number_input("ID of the product.", min_value=1, step=1)
        adress = st.text_input("Your Adress:")
        p_i_no = st.text_input("Your Identity Number:", max_chars=11)
        CVV_n = st.text_input("CVV number of your card: ", max_chars=3)
        card_no = st.text_input("Your card number: ")
        c_e_mail = st.text_input("Your E-Mail address: ")
        buy_product_button = st.form_submit_button("Buy Product")

        if p_i_no:
            if len(p_i_no) == 11 and p_i_no.isdigit():
                st.success("Valid identity number.")
            else:
                st.error("Please enter a valid 11-digit identity number consisting of numbers only.")

        if buy_product_button:
            try:
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM products WHERE product_id=?", (p_id,))
                result = cursor.fetchone()

                if result:
                    cursor.execute("INSERT INTO customers (identity_no, CVV, card_no, address, e_mail) VALUES (?, ?, ?, ?, ?)", (p_i_no, CVV_n, card_no, adress, c_e_mail))
                    cursor.execute("UPDATE products SET purchase_count=purchase_count+1 WHERE product_id=?", (p_id,))
                    conn.commit()
                    conn.close()
                    st.success("Product purchased successfully.")
                else:
                    st.warning("Product ID is wrong, please try again.")

            except:
                conn.rollback()
                conn.close()
                st.error("There is an error, please try again.")

elif choice == "See or Delete Your Products":

    with st.form("see_your_products"):
        st.write("See Your Products")
        sy_username = st.text_input("Your username: ")
        sy_password = st.text_input("Your password: ", type="password")
        see_products = st.form_submit_button("See Your Products")

        if see_products:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT seller_id FROM sellers WHERE user_name = ? AND password = ?", (sy_username, sy_password))
            seller = cursor.fetchone()

            if seller:
                seller_id = seller[0]
                query = """
                    SELECT p.product_name, p.price, p.purchase_count
                    FROM products p
                    WHERE p.seller_id = ?
                """
                product_data = pd.read_sql_query(query, conn, params=(seller_id,))
                st.write("Your Products and Sales Summary:")
                st.dataframe(product_data)
                conn.close()
                fig, ax = plt.subplots()
                ax.bar(product_data['product_name'], product_data['purchase_count'], color='skyblue')
                ax.set_xlabel('Product Name')
                ax.set_ylabel('Total Sold')
                ax.set_title('Sales Count per Product')
                ax.tick_params(axis='x', rotation=45)
                st.pyplot(fig)
                total_sales = product_data['purchase_count'].sum()
                total_revenue = (product_data['price'] * product_data['purchase_count']).sum()
                st.write(f"Total Products Sold: {total_sales}")
                st.write(f"Total Revenue: ${total_revenue:.2f}")
            else:
                st.warning("Username and password do not match. Please try again.")
            
    with st.form("delete_product"):
        st.write("Delete product")
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        de_username = st.text_input("Your Username:")
        de_password = st.text_input("Your Password:", type="password")
        p_id = st.number_input("Your product ID: ", min_value=1, step=1)
        delete_product = st.form_submit_button("Delete")

        if delete_product:
            try:
                    cursor.execute("SELECT seller_id FROM sellers WHERE user_name = ? AND password = ?", (de_username, de_password))
                    seller = cursor.fetchone()

                    if seller:
                        seller_id = seller[0]
                        cursor.execute("SELECT seller_id FROM products WHERE product_id = ?", (p_id,))
                        product = cursor.fetchone()

                        if product and product[0] == seller_id:

                            cursor.execute("DELETE FROM products WHERE product_id = ?", (p_id,))
                            conn.commit()
                            st.success(f"Product ID {p_id} deleted successfully.")
                        else:
                            st.warning("You are not authorized to delete this product.")
                    else:
                        st.error("Login failed! Incorrect username or password.")
            except Exception as e:
                    st.error(f"Error: {e}")
            finally:
                    conn.close()

elif choice == "Sales Analysis":
    st.title("Sales Analysis")
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    query = """
        SELECT p.product_name, p.price, p.purchase_count, s.user_name
        FROM products p
        JOIN sellers s ON p.seller_id = s.seller_id
    """

    sales_data = pd.read_sql_query(query, conn)

    if not sales_data.empty:
        st.subheader("Sales Data")
        st.dataframe(sales_data)

        st.subheader("Sales Analysis Graphs")

        # Total Sales per Product
        fig1 = px.bar(sales_data, x="product_name", y="purchase_count", title="Total Sales per Product", color="user_name")
        st.plotly_chart(fig1)

        # Revenue per Product
        sales_data["revenue"] = sales_data["price"] * sales_data["purchase_count"]
        fig2 = px.pie(sales_data, values="revenue", names="product_name", title="Revenue Distribution by Product")
        st.plotly_chart(fig2)

        # Top Sellers by Revenue
        revenue_by_seller = sales_data.groupby("user_name")["revenue"].sum().reset_index()
        fig3 = px.bar(revenue_by_seller, x="user_name", y="revenue", title="Revenue by Seller", color="user_name")
        st.plotly_chart(fig3)

    else:
        st.warning("No sales data available.")

    conn.close()
import streamlit as st
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

if prediction > 2500:
    discount = 20
elif prediction > 2000:
    discount = 10
elif prediction > 1500:
    discount = 5
else:
    discount = 0

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

# Streamlit page configuration
st.set_page_config(
    page_title="Re-sell-Leftovers",
    layout="centered",
    initial_sidebar_state="expanded",
    page_icon="🍽"
)

with st.sidebar:
    st.title("Navigation")
    choice = st.radio("Menu", ["Create Account to Sell", "Sell Product", "Search Product", "Buy Product", "See or Delete Your Products", "View Product Price Distribution"])

# Logic for each menu choice
if choice == "Create Account to Sell":
    st.title("Welcome to Re-sell-Leftovers :wave: Create an Account and Help Prevent Waste")
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
    st.title("Search for Products")
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    search_query = st.text_input("Enter product name to search:")
    if st.button("Search"):
        cursor.execute("SELECT product_name, description, price, discount, product_image_path FROM products WHERE product_name LIKE ?", (f"%{search_query}%",))
        products = cursor.fetchall()
        if products:
            for product in products:
                st.write("Name:", product[0])
                st.write("Description:", product[1])
                st.write("Price:", product[2])
                st.write("Discount:", product[3])
                if product[4] and os.path.exists(product[4]):
                    st.image(product[4])
        else:
            st.write("No products found.")

elif choice == "Buy Product":
    st.title("Buy a Product")
    st.write("Enter the Product ID to make a purchase.")

    with st.form("purchase_form"):
        product_id = st.text_input("Product ID:")
        customer_identity = st.text_input("Your Identity Number:", max_chars=11)
        cvv = st.text_input("CVV:", max_chars=3)
        card_no = st.text_input("Card Number:")
        address = st.text_area("Shipping Address:")
        email = st.text_input("Your Email Address:")
        submit_purchase = st.form_submit_button("Buy Now")

        if submit_purchase:
            if product_id and customer_identity and cvv and card_no and address and email:
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
                product = cursor.fetchone()
                if product:
                    cursor.execute("INSERT INTO customers (identity_no, CVV, card_no, address, e_mail) VALUES (?, ?, ?, ?, ?)",
                                   (customer_identity, cvv, card_no, address, email))
                    conn.commit()
                    st.success("Purchase successful. Thank you for shopping with us!")
                else:
                    st.error("Product not found. Please enter a valid Product ID.")
                conn.close()
            else:
                st.error("Please fill in all the fields.")

elif choice == "See or Delete Your Products":
    st.title("See or Delete Your Products")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Get the logged-in seller and fetch their products
    username = st.text_input("Enter your username:")
    password = st.text_input("Enter your password:", type="password")
    if st.button("Fetch Products"):
        cursor.execute("SELECT seller_id FROM sellers WHERE user_name = ? AND password = ?", (username, password))
        seller = cursor.fetchone()
        
        if seller:
            seller_id = seller[0]
            cursor.execute("SELECT product_id, product_name FROM products WHERE seller_id = ?", (seller_id,))
            products = cursor.fetchall()

            if products:
                st.write("Here are your products:")
                for product in products:
                    st.write(f"Product Name: {product[1]}, Product ID: {product[0]}")
                
                # Delete a product
                product_to_delete = st.text_input("Enter the Product ID to delete:")
                if st.button("Delete Product"):
                    if product_to_delete:
                        cursor.execute("SELECT * FROM products WHERE product_id = ? AND seller_id = ?", 
                                       (product_to_delete, seller_id))
                        product = cursor.fetchone()
                        if product:
                            cursor.execute("DELETE FROM products WHERE product_id = ?", (product_to_delete,))
                            conn.commit()
                            st.success(f"Product with ID {product_to_delete} has been deleted successfully!")
                        else:
                            st.error("Product not found or you do not have permission to delete this product.")
                    else:
                        st.error("Please enter a valid product ID.")
            else:
                st.write("You don't have any products listed.")
        else:
            st.error("Invalid username or password.")
    
    conn.close()


elif choice == "View Product Price Distribution":
    st.title("Product Price Distribution and Seller Performance")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Fetch product prices for price distribution
    cursor.execute("SELECT price FROM products")
    prices = [row[0] for row in cursor.fetchall()]

    # Fetch seller performance data
    cursor.execute("""
        SELECT s.user_name, SUM(p.purchase_count) AS total_sold
        FROM sellers s
        JOIN products p ON s.seller_id = p.seller_id
        GROUP BY s.user_name
        ORDER BY total_sold DESC
    """)
    seller_data = cursor.fetchall()

    conn.close()

    # Price Distribution Graph
    if prices:
        fig_price = px.histogram(prices, nbins=10, labels={'value': 'Price'}, title="Distribution of Product Prices")
        st.plotly_chart(fig_price)
    else:
        st.write("No products available for price visualization.")

    # Seller Performance Graph
    if seller_data:
        seller_names = [row[0] for row in seller_data]
        total_sold = [row[1] for row in seller_data]

        fig_seller = px.bar(
            x=seller_names,
            y=total_sold,
            labels={'x': 'Seller Username', 'y': 'Products Sold'},
            title="Products Sold by Each Seller"
        )
        st.plotly_chart(fig_seller)
    else:
        st.write("No seller data available for visualization.")

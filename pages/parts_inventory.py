import streamlit as st
import pandas as pd
from utils.gsheet_db import read_all_rows, append_row, update_row, delete_row
from datetime import datetime

st.set_page_config(page_title="Parts Inventory - Speed Lab", page_icon="\ud83d\udd27", layout="wide")

if not st.session_state.get("authenticated"):
    st.warning("Please log in from the Home page.")
    st.stop()

st.title("\ud83d\udd27 Parts Inventory")
st.markdown("Track spare parts, consumables, and supplies for race night.")

# --- Load Data ---
parts = read_all_rows("parts_inventory")
df = pd.DataFrame(parts) if parts else pd.DataFrame()

tab1, tab2 = st.tabs(["\ud83d\udce6 Inventory List", "\u2795 Add Part"])

# --- Inventory List ---
with tab1:
    if df.empty:
        st.info("No parts in inventory yet. Add your first part!")
    else:
        st.subheader("Current Inventory")

        # Filters
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            cat_filter = st.selectbox("Filter by Category", ["All"] + sorted(df["category"].unique().tolist()) if "category" in df.columns else ["All"])
        with fc2:
            search = st.text_input("Search Parts", placeholder="Part name or number...")
        with fc3:
            low_stock = st.checkbox("Show Low Stock Only")

        filtered = df.copy()
        if cat_filter != "All" and "category" in filtered.columns:
            filtered = filtered[filtered["category"] == cat_filter]
        if search:
            mask = filtered.apply(lambda row: search.lower() in str(row).lower(), axis=1)
            filtered = filtered[mask]
        if low_stock and "quantity" in filtered.columns and "min_quantity" in filtered.columns:
            filtered["quantity"] = pd.to_numeric(filtered["quantity"], errors="coerce")
            filtered["min_quantity"] = pd.to_numeric(filtered["min_quantity"], errors="coerce")
            filtered = filtered[filtered["quantity"] <= filtered["min_quantity"]]

        # Display
        if not filtered.empty:
            display_cols = [c for c in ["part_name", "part_number", "category", "quantity", "min_quantity", "location", "supplier", "cost"] if c in filtered.columns]
            st.dataframe(filtered[display_cols] if display_cols else filtered, use_container_width=True, hide_index=True)

            # Low stock alerts
            if "quantity" in df.columns and "min_quantity" in df.columns:
                check_df = df.copy()
                check_df["quantity"] = pd.to_numeric(check_df["quantity"], errors="coerce")
                check_df["min_quantity"] = pd.to_numeric(check_df["min_quantity"], errors="coerce")
                low = check_df[check_df["quantity"] <= check_df["min_quantity"]]
                if not low.empty:
                    st.warning(f"\u26a0\ufe0f {len(low)} part(s) at or below minimum stock level!")
                    for _, row in low.iterrows():
                        st.markdown(f"- **{row.get('part_name', 'Unknown')}**: {row.get('quantity', '?')} remaining (min: {row.get('min_quantity', '?')})")
        else:
            st.info("No parts match your filters.")

        # Edit / Delete section
        st.markdown("---")
        st.subheader("Edit or Remove Part")
        if "part_name" in df.columns:
            part_names = df["part_name"].tolist()
            selected = st.selectbox("Select Part to Edit", part_names)
            idx = part_names.index(selected)

            with st.form("edit_part"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    new_qty = st.number_input("Update Quantity", value=int(df.iloc[idx].get("quantity", 0)), min_value=0)
                    new_cost = st.text_input("Update Cost", value=str(df.iloc[idx].get("cost", "")))
                with ec2:
                    new_location = st.text_input("Update Location", value=str(df.iloc[idx].get("location", "")))
                    new_notes = st.text_input("Update Notes", value=str(df.iloc[idx].get("notes", "")))

                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.form_submit_button("Update Part", type="primary"):
                        updates = {"quantity": str(new_qty), "cost": new_cost, "location": new_location, "notes": new_notes, "updated": str(datetime.now())}
                        update_row("parts_inventory", idx, updates)
                        st.success(f"{selected} updated!")
                        st.rerun()
                with bc2:
                    if st.form_submit_button("\ud83d\uddd1\ufe0f Delete Part"):
                        delete_row("parts_inventory", idx)
                        st.success(f"{selected} removed from inventory.")
                        st.rerun()

# --- Add Part ---
with tab2:
    st.subheader("Add New Part")
    with st.form("add_part"):
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            part_name = st.text_input("Part Name*")
            part_number = st.text_input("Part Number")
            category = st.selectbox("Category", [
                "Engine", "Suspension", "Brakes", "Drivetrain", "Electrical",
                "Body/Aero", "Safety", "Consumables", "Hardware", "Other"
            ])
        with ac2:
            quantity = st.number_input("Quantity", min_value=0, value=1)
            min_quantity = st.number_input("Minimum Stock Level", min_value=0, value=1)
            location = st.text_input("Storage Location", placeholder="e.g., Trailer Shelf 2")
        with ac3:
            supplier = st.text_input("Supplier")
            cost = st.text_input("Cost per Unit", placeholder="e.g., 24.99")
            notes = st.text_area("Notes", height=100)

        if st.form_submit_button("Add Part to Inventory", type="primary"):
            if not part_name:
                st.error("Part name is required.")
            else:
                append_row("parts_inventory", {
                    "part_name": part_name, "part_number": part_number,
                    "category": category, "quantity": str(quantity),
                    "min_quantity": str(min_quantity), "location": location,
                    "supplier": supplier, "cost": cost, "notes": notes,
                    "created": str(datetime.now()), "updated": str(datetime.now())
                })
                st.success(f"{part_name} added to inventory!")
                st.rerun()

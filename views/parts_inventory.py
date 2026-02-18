import streamlit as st
import pandas as pd
from utils.gsheet_db import read_sheet, append_row, update_row, delete_row, timestamp_now


def render():
    st.header("📦 Parts Inventory")
    st.markdown("Track spare parts, consumables, and supplies for race night.")

    df = read_sheet("parts")

    tab1, tab2 = st.tabs(["Inventory List", "Add Part"])

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
                        st.warning(f"{len(low)} part(s) at or below minimum stock level!")
                        for _, row in low.iterrows():
                            st.markdown(f"- **{row.get('part_name', 'Unknown')}**: {row.get('quantity', '?')} remaining (min: {row.get('min_quantity', '?')})")
            else:
                st.info("No parts match your filters.")

            # Delete section
            st.divider()
            if "part_name" in df.columns:
                del_name = st.selectbox("Select part to delete", df["part_name"].tolist())
                if st.button("Delete Selected Part", type="secondary"):
                    row_idx = df[df["part_name"] == del_name].index[0] + 2
                    delete_row("parts", row_idx)
                    st.success(f"Deleted {del_name}")
                    st.rerun()

    # --- Add Part ---
    with tab2:
        with st.form("add_part", clear_on_submit=True):
            st.subheader("Add New Part")
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                part_name = st.text_input("Part Name *")
                part_number = st.text_input("Part Number")
                category = st.selectbox("Category", [
                    "Engine", "Suspension", "Brakes", "Drivetrain",
                    "Electrical", "Body/Aero", "Safety", "Consumables",
                    "Hardware", "Other"
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
                    append_row("parts", {
                        "part_name": part_name, "part_number": part_number,
                        "category": category, "quantity": str(quantity),
                        "min_quantity": str(min_quantity), "location": location,
                        "supplier": supplier, "cost": cost,
                        "notes": notes, "created": timestamp_now(),
                    })
                    st.success(f"{part_name} added to inventory!")
                    st.rerun()

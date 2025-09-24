import streamlit as st
import pandas as pd
import datetime

def parse_identifier(line: str) -> tuple[datetime.date, str] | None:
    """
    Parses a line like '250910_DOP' into a date object and a tag string.

    Args:
        line (str): A single line from the input file.

    Returns:
        A tuple (datetime.date, str) or None if parsing fails.
    """
    parts = line.strip().split("_")
    if len(parts) != 2 or len(parts[0]) != 6:
        return None
    date_str, tag = parts
    try:
        year = 2000 + int(date_str[0:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        return datetime.date(year, month, day), tag
    except (ValueError, IndexError):
        return None


def render_holo_section(combined_df: pd.DataFrame) -> pd.DataFrame:
    """
    Renders the Holo Data filters and dataframe.

    Args:
        combined_df (pd.DataFrame): The full dataframe from the database.

    Returns:
        pd.DataFrame: The dataframe filtered by the user's selections.
    """
    st.header("Holo Data")

    filtered_holo_df = combined_df.copy()
    if filtered_holo_df.empty:
        return filtered_holo_df

    uploaded_file = st.file_uploader(
        "Import group (.txt)",
        type=["txt"],
        help="Upload a .txt file with one identifier per line (e.g., 240115_ABC)",
    )

    is_disabled = uploaded_file is not None
    filtered_holo_df["holo_created_date"] = pd.to_datetime(
        filtered_holo_df["holo_created_at"]
    ).dt.date

    if is_disabled:
        identifiers_to_match = []
        try:
            content = uploaded_file.getvalue().decode("utf-8")
            lines = content.splitlines()

            for line in lines:
                if line.strip():
                    parsed = parse_identifier(line)
                    if parsed:
                        identifiers_to_match.append(parsed)
                    else:
                        st.warning(f"Could not parse identifier: '{line.strip()}'")
        except Exception as e:
            st.error(f"Error reading or parsing file: {e}")

        if identifiers_to_match:
            mask = pd.Series([False] * len(filtered_holo_df), index=filtered_holo_df.index)
            for date_to_match, tag_to_match in identifiers_to_match:
                condition = (
                    filtered_holo_df["holo_created_date"] == date_to_match
                ) & (filtered_holo_df["measure_tag"] == tag_to_match)
                mask |= condition
            filtered_holo_df = filtered_holo_df[mask]
            st.info(
                f"Filtered by imported group ({len(identifiers_to_match)} identifiers)."
            )

    # --- Setup Filter Controls ---
    base_date_col = pd.to_datetime(combined_df["holo_created_at"]).dt.date
    min_date = base_date_col.min() if not base_date_col.empty else datetime.date.today()
    max_date = base_date_col.max() if not base_date_col.empty else datetime.date.today()
    unique_tags = sorted(combined_df["measure_tag"].dropna().unique())

    selected_date_range = st.date_input(
        "Filter by creation date",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        disabled=is_disabled,
    )
    
    selected_tags = st.multiselect(
        "Filter by measure tag",
        options=unique_tags,
        disabled=is_disabled,
    )

    if not is_disabled:
        if len(selected_date_range) == 2:
            start_date, end_date = selected_date_range
            filtered_holo_df = filtered_holo_df[
                filtered_holo_df["holo_created_date"].between(start_date, end_date)
            ]
        
        if selected_tags:
            filtered_holo_df = filtered_holo_df[
                filtered_holo_df["measure_tag"].isin(selected_tags)
            ]

    total_holo_files = combined_df["holo_file"].nunique()
    shown_holo_files = filtered_holo_df["holo_file"].nunique()

    holo_display_df = (
        filtered_holo_df[["holo_file", "measure_tag", "holo_created_at"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    with st.expander(f"**Show {shown_holo_files} of {total_holo_files} .holo files.**"):
        st.dataframe(holo_display_df, width='stretch')
        st.download_button(
            label="Export paths to .txt",
            data="\n".join(holo_display_df["holo_file"].unique()),
            file_name="holo_files.txt",
            mime="text/plain",
        )

    return filtered_holo_df.drop(columns=["holo_created_date"])
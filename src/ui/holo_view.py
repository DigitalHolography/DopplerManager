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
    st.header("1. Holo Data")

    base_holo_df = combined_df.copy()

    # --- New file uploader for group import ---
    uploaded_file = st.file_uploader(
        "Import group (.txt)",
        type=["txt"],
        help="Upload a .txt file with one identifier per line (e.g., 240115_ABC)",
    )

    if uploaded_file:
        # Ensure the creation date column is in a comparable format (date object)
        base_holo_df["holo_created_date"] = pd.to_datetime(
            base_holo_df["holo_created_at"]
        ).dt.date

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
            # Create a boolean mask to filter the dataframe
            mask = pd.Series([False] * len(base_holo_df), index=base_holo_df.index)

            for date_to_match, tag_to_match in identifiers_to_match:
                condition = (
                    base_holo_df["holo_created_date"] == date_to_match
                ) & (base_holo_df["measure_tag"] == tag_to_match)
                mask |= condition  # Add matching rows to the mask

            # Apply the filter and drop the temporary date column
            base_holo_df = base_holo_df[mask].drop(columns=["holo_created_date"])
            st.info(
                f"Filtered by imported group. Found data for {len(base_holo_df['holo_file'].unique())} of {len(identifiers_to_match)} identifiers."
            )

    # The multiselect now operates on the dataframe that may have been filtered by the file
    unique_tags = sorted(base_holo_df["measure_tag"].dropna().unique())
    selected_tags = st.multiselect(
        "Filter by measure tag", options=unique_tags, default=unique_tags if uploaded_file else None
    )

    filtered_holo_df = base_holo_df.copy()
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
    st.markdown(f"**Showing {shown_holo_files} of {total_holo_files} .holo files.**")
    st.dataframe(holo_display_df, width='stretch')

    # Expander for .holo files without HD renders
    holo_with_no_hd = filtered_holo_df[filtered_holo_df["hd_folder"].isnull()]
    if not holo_with_no_hd.empty:
        with st.expander(
            f"Show {holo_with_no_hd['holo_file'].nunique()} .holo files with no HoloDoppler renders"
        ):
            st.warning(
                "The following .holo files do not have any associated HoloDoppler renders."
            )
            st.dataframe(
                holo_with_no_hd[["holo_file", "measure_tag", "holo_created_at"]]
                .drop_duplicates()
                .reset_index(drop=True),
                width='stretch',
            )

    st.markdown("---")
    return filtered_holo_df
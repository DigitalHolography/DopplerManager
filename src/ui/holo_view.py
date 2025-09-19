import streamlit as st
import pandas as pd

def render_holo_section(combined_df: pd.DataFrame) -> pd.DataFrame:
    """
    Renders the Holo Data filters and dataframe.

    Args:
        combined_df (pd.DataFrame): The full dataframe from the database.

    Returns:
        pd.DataFrame: The dataframe filtered by the user's selections.
    """
    st.header("1. Holo Data")
    unique_tags = sorted(combined_df["measure_tag"].dropna().unique())
    selected_tags = st.multiselect("Filter by measure tag", options=unique_tags)

    filtered_holo_df = combined_df.copy()
    if selected_tags:
        filtered_holo_df = filtered_holo_df[
            filtered_holo_df["measure_tag"].isin(selected_tags)
        ]

    total_holo_files = combined_df["holo_file"].nunique()
    shown_holo_files = filtered_holo_df["holo_file"].nunique()

    holo_display_df = (
        filtered_holo_df[["holo_file", "measure_tag"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    st.markdown(f"**Showing {shown_holo_files} of {total_holo_files} .holo files.**")
    st.dataframe(holo_display_df, width="stretch")

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
                holo_with_no_hd[["holo_file", "measure_tag"]]
                .drop_duplicates()
                .reset_index(drop=True),
                width="stretch",
            )

    st.markdown("---")
    return filtered_holo_df
import streamlit as st
import pandas as pd

def render_hd_ef_section(filtered_holo_df: pd.DataFrame) -> None:
    """
    Renders the HoloDoppler and EyeFlow sections based on the
    pre-filtered holo data.
    """
    # --- 2. HoloDoppler Filters & Data ---
    st.header("2. HoloDoppler Data")
    hd_base_df = filtered_holo_df.dropna(subset=["hd_folder"])

    if hd_base_df.empty:
        st.info("No HoloDoppler data matches the current Holo filters.")
        return

    unique_hd_versions = sorted(hd_base_df["hd_version"].dropna().unique())
    selected_hd_versions = st.multiselect(
        "Filter by HoloDoppler version", options=unique_hd_versions
    )

    filtered_hd_df = hd_base_df.copy()
    if selected_hd_versions:
        filtered_hd_df = filtered_hd_df[
            filtered_hd_df["hd_version"].isin(selected_hd_versions)
        ]

    total_hd_in_selection = hd_base_df["hd_folder"].nunique()
    shown_hd_folders = filtered_hd_df["hd_folder"].nunique()

    hd_display_df = (
        filtered_hd_df[["hd_folder", "measure_tag", "hd_version"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    st.markdown(
        f"**Showing {shown_hd_folders} of {total_hd_in_selection} HoloDoppler folders from the selection above.**"
    )
    st.dataframe(hd_display_df, width="stretch")

    hd_with_no_ef = filtered_hd_df[filtered_hd_df["ef_folder"].isnull()]
    if not hd_with_no_ef.empty:
        with st.expander(
            f"Show {hd_with_no_ef['hd_folder'].nunique()} HoloDoppler folders with no EyeFlow renders"
        ):
            st.warning(
                "The following HoloDoppler folders do not have any associated EyeFlow renders."
            )
            st.dataframe(
                hd_with_no_ef[["hd_folder", "measure_tag", "hd_version"]]
                .drop_duplicates()
                .reset_index(drop=True),
                width="stretch",
            )

    st.markdown("---")

    # --- 3. EyeFlow Filters & Data ---
    st.header("3. EyeFlow Data")
    ef_base_df = filtered_hd_df.dropna(subset=["ef_folder"])

    if not ef_base_df.empty:
        unique_ef_versions = sorted(ef_base_df["ef_version"].dropna().unique())
        selected_ef_versions = st.multiselect(
            "Filter by EyeFlow version", options=unique_ef_versions
        )

        ef_display_df = ef_base_df.copy()
        if selected_ef_versions:
            ef_display_df = ef_display_df[
                ef_display_df["ef_version"].isin(selected_ef_versions)
            ]

        total_ef_in_selection = ef_base_df["ef_folder"].nunique()
        shown_ef_folders = ef_display_df["ef_folder"].nunique()

        st.markdown(
            f"**Showing {shown_ef_folders} of {total_ef_in_selection} EyeFlow folders from the selection above.**"
        )
        ef_display_columns = ["ef_folder", "ef_version"]
        st.dataframe(
            ef_display_df[ef_display_columns]
            .drop_duplicates()
            .reset_index(drop=True),
            width="stretch",
        )
    else:
        st.info("No EyeFlow data matches the current HoloDoppler filters.")
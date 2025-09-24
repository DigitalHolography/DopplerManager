import streamlit as st
import pandas as pd

def render_ef_section(filtered_hd_df: pd.DataFrame) -> pd.DataFrame:
    """
    Renders the EyeFlow section of the dashboard.
    
    Args:
        filtered_hd_df (pd.DataFrame): DataFrame filtered by HoloDoppler selections.

    Returns:
        pd.DataFrame: DataFrame filtered by EyeFlow selections.
    """
    st.header("EyeFlow Data")
    ef_base_df = filtered_hd_df.dropna(subset=["ef_folder"]).copy()

    if ef_base_df.empty:
        st.info("No EyeFlow data matches the current HoloDoppler filters.")
        with st.expander(
            f"Show {filtered_hd_df["hd_folder"].nunique()} HoloDoppler folders with no EyeFlow renders"
        ):
            st.warning(
                "The following HoloDoppler folders do not have any associated EyeFlow renders."
            )
            st.dataframe(
                filtered_hd_df[["hd_folder", "measure_tag", "hd_version"]]
                .drop_duplicates()
                .reset_index(drop=True),
                width="stretch",
            )
            st.download_button(
                label="Export paths to .txt",
                data="\n".join(filtered_hd_df["hd_folder"].unique()),
                file_name="ef_batch_input.txt",
                mime="text/plain",
            )
        return ef_base_df

    if st.checkbox("Latest EF render only", value=True):
        latest_indices = ef_base_df.loc[
            ef_base_df.groupby("hd_folder")["ef_render_number"].idxmax()
        ]
        ef_base_df = latest_indices.copy()
        
    unique_ef_versions = sorted(ef_base_df["ef_version"].dropna().unique())
    selected_ef_versions = st.multiselect(
        "Filter by EyeFlow version", options=unique_ef_versions
    )

    filtered_ef_df = ef_base_df.copy()
    if selected_ef_versions:
        filtered_ef_df = filtered_ef_df[
            filtered_ef_df["ef_version"].isin(selected_ef_versions)
        ]

    total_ef_in_selection = ef_base_df["ef_folder"].nunique()
    shown_ef_folders = filtered_ef_df["ef_folder"].nunique()

    ef_display_df = (
        filtered_ef_df[["ef_folder", "measure_tag", "ef_version"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    with st.expander(
            f"**Show {shown_ef_folders} of {total_ef_in_selection} EyeFlow folders from the selection above.**"
        ):
        st.dataframe(ef_display_df, width="stretch")
        st.download_button(
            label="Export paths to .txt",
            data="\n".join(ef_display_df["ef_folder"].unique()),
            file_name="ef_folder_paths.txt",
            mime="text/plain",
        )

    hd_folders_with_matching_renders = filtered_ef_df["hd_folder"].unique()
    hd_with_no_matching_ef = filtered_hd_df[
        ~filtered_hd_df["hd_folder"].isin(hd_folders_with_matching_renders)
    ]

    if not hd_with_no_matching_ef.empty:
        with st.expander(
            f"**Show {hd_with_no_matching_ef["hd_folder"].nunique()} HoloDoppler folders with no matching EyeFlow renders**"
        ):
            st.warning(
                "The following HoloDoppler folders do not have any EyeFlow renders that match the version filter above (or have no renders at all)."
            )
            st.dataframe(
                hd_with_no_matching_ef[["hd_folder", "measure_tag", "hd_version"]]
                .drop_duplicates()
                .reset_index(drop=True),
                width="stretch",
            )
            
            st.download_button(
                label="Export paths to .txt",
                data="\n".join(hd_with_no_matching_ef["hd_folder"].unique()),
                file_name="ef_batch_input.txt",
                mime="text/plain",
            )
    return filtered_ef_df
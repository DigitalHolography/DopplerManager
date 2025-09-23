import streamlit as st
import pandas as pd

def render_hd_section(filtered_holo_df: pd.DataFrame) -> pd.DataFrame:
    """
    Renders the HoloDoppler and EyeFlow sections based on the
    pre-filtered holo data.

    Args:   
        filtered_holo_df (pd.DataFrame): DataFrame filtered by Holo selections.

    Returns:
        pd.DataFrame: DataFrame further filtered by HoloDoppler selections.
    """
    st.header("HoloDoppler Data")
    hd_base_df = filtered_holo_df.copy().dropna(subset=["hd_folder"])

    if hd_base_df.empty:
        st.info("No HoloDoppler data matches the current Holo filters.")
        with st.expander(
            f"Show {filtered_holo_df['holo_file'].nunique()} .holo files with no HoloDoppler renders"
        ):
            st.warning(
                "The following .holo files do not have any associated HoloDoppler renders."
            )
            st.dataframe(
                filtered_holo_df[["holo_file", "measure_tag", "holo_created_at"]]
                .drop_duplicates()
                .reset_index(drop=True),
                width="stretch",
            )
            st.download_button(
                label="Export paths to .txt",
                data="\n".join(filtered_holo_df["holo_file"].unique()),
                file_name="hd_batch_input.txt",
                mime="text/plain",
            )
        return hd_base_df

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

    with st.expander(
            f"**Show {shown_hd_folders} of {total_hd_in_selection} HoloDoppler folders from the selection above.**"
        ):
        st.dataframe(hd_display_df, width="stretch")
        st.download_button(
                label="Export paths to .txt",
                data="\n".join(hd_display_df["hd_folder"].unique()),
                file_name="hd_folders.txt",
                mime="text/plain",
            )

    holo_files_with_matching_renders = filtered_hd_df["holo_file"].unique()
    holo_with_no_matching_hd = filtered_holo_df[
        ~filtered_holo_df["holo_file"].isin(holo_files_with_matching_renders)
    ]

    if not holo_with_no_matching_hd.empty:
        with st.expander(
            f"**Show {holo_with_no_matching_hd['holo_file'].nunique()} .holo files with no matching HoloDoppler renders**"
        ):
            st.warning(
                "The following .holo files do not have any HoloDoppler renders that match the version filter above (or have no renders at all)."
            )
            st.dataframe(
                holo_with_no_matching_hd[["holo_file", "measure_tag", "holo_created_at"]]
                .drop_duplicates()
                .reset_index(drop=True),
                width="stretch",
            )
            st.download_button(
                label="Export paths to .txt",
                data="\n".join(holo_with_no_matching_hd["holo_file"].unique()),
                file_name="hd_batch_input.txt",
                mime="text/plain",
            )
    return filtered_hd_df
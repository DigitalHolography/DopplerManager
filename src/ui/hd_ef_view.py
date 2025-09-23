import streamlit as st
import pandas as pd

def render_hd_ef_section(filtered_holo_df: pd.DataFrame) -> None:
    """
    Renders the HoloDoppler and EyeFlow sections based on the
    pre-filtered holo data.
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


    st.markdown("---")

    st.header("EyeFlow Data")
    # Base for this section is data already filtered by HoloDoppler version
    ef_base_df = filtered_hd_df.dropna(subset=["hd_folder"]).copy()

    if ef_base_df.empty:
        st.info("No EyeFlow data matches the current HoloDoppler filters.")
        return
        
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

    # --- Expander for HD folders with no *matching* EF renders ---
    hd_folders_with_matching_renders = ef_display_df.dropna(subset=['ef_folder'])['hd_folder'].unique()
    hd_with_no_matching_ef = ef_base_df[
        ~ef_base_df['hd_folder'].isin(hd_folders_with_matching_renders)
    ]

    if not hd_with_no_matching_ef.empty:
        with st.expander(
            f"Show {hd_with_no_matching_ef['hd_folder'].nunique()} HoloDoppler folders with no matching EyeFlow renders"
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
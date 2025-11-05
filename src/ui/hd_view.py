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
    # Only consider HD renders that have a raw h5 file and a version.txt.
    hd_base_df = filtered_holo_df.dropna(
        subset=["hd_folder", "hd_raw_h5_path", "hd_version"]
    ).copy()

    if hd_base_df.empty:
        st.info(
            "No HoloDoppler data with a raw .h5 file matches the current Holo filters."
        )
        with st.expander(
            f"Show {filtered_holo_df['holo_file'].nunique()} .holo files with no valid HoloDoppler renders"
        ):
            st.warning(
                "The following .holo files do not have any associated HoloDoppler renders with a raw .h5 file."
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

    if st.checkbox("Latest HD render only", value=True):
        latest_hd_render_numbers = hd_base_df.groupby("holo_file")[
            "hd_render_number"
        ].transform("max")
        hd_base_df = hd_base_df[
            hd_base_df["hd_render_number"] == latest_hd_render_numbers
        ]

    unique_hd_versions = sorted(hd_base_df["hd_version"].dropna().unique())
    selected_hd_versions = st.multiselect(
        "Filter by HoloDoppler version", options=unique_hd_versions
    )

    filtered_hd_df = hd_base_df
    if selected_hd_versions:
        filtered_hd_df = filtered_hd_df[
            filtered_hd_df["hd_version"].isin(selected_hd_versions)
        ]

    total_hd_in_selection = hd_base_df["hd_folder"].nunique()
    shown_hd_folders = filtered_hd_df["hd_folder"].nunique()

    hd_display_df = (
        filtered_hd_df[["hd_folder", "measure_tag", "hd_version", "hd_raw_h5_path"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    with st.expander(
        f"**Show {shown_hd_folders} of {total_hd_in_selection} valid HoloDoppler folders from the selection above.**"
    ):
        st.dataframe(hd_display_df, width="stretch")
    st.download_button(
        label="Export paths to .txt",
        data="\n".join(hd_display_df["hd_folder"].unique()),
        file_name="hd_folder_paths.txt",
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
                "The following .holo files do not have any HoloDoppler renders that match the filter above, have no renders at all, or are missing the raw .h5 file or the version.txt."
            )
            st.dataframe(
                holo_with_no_matching_hd[
                    ["holo_file", "measure_tag", "holo_created_at"]
                ]
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

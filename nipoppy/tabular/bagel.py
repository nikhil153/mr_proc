"""Class for bagel tracker files."""

from typing import Any, Optional

from pydantic import Field, field_validator, model_validator

from nipoppy.tabular.base import BaseTabular, BaseTabularModel
from nipoppy.utils import (
    FIELD_DESCRIPTION_MAP,
    check_participant_id,
    check_session_id,
    participant_id_to_bids_participant_id,
    session_id_to_bids_session_id,
)

STATUS_SUCCESS = "SUCCESS"
STATUS_FAIL = "FAIL"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_UNAVAILABLE = "UNAVAILABLE"


class BagelModel(BaseTabularModel):
    """
    A file generated by the trackers.

    Contains processing statuses for image processing pipelines.

    Note: This class is called "model" to be consistent with Pydantic nomenclature,
    but it can be thought of as a schema for each row in the bagel file.
    """

    participant_id: str = Field(
        title="Participant ID",
        description=f"{FIELD_DESCRIPTION_MAP['participant_id']} (as in the manifest)",
    )
    bids_participant_id: str = Field(
        title="BIDS participant ID",
        description=FIELD_DESCRIPTION_MAP["bids_participant_id"],
    )
    session_id: str = Field(description=FIELD_DESCRIPTION_MAP["session_id"])
    bids_session_id: str = Field(description=FIELD_DESCRIPTION_MAP["bids_session_id"])
    pipeline_name: str = Field(description="The name of the pipeline being tracked")
    pipeline_version: str = Field(
        description="The version of the pipeline being tracked"
    )
    pipeline_step: str = Field(
        description="The name of the pipeline step being tracked",
    )
    status: str = Field(
        description="The status of the pipeline run for this participant-visit pair"
    )

    @field_validator("status")
    @classmethod
    def check_status(cls, value: str):
        """Check that a status field has a valid value."""
        valid_statuses = [
            STATUS_SUCCESS,
            STATUS_FAIL,
            STATUS_INCOMPLETE,
            STATUS_UNAVAILABLE,
        ]
        if value not in valid_statuses:
            raise ValueError(
                f"Invalid status '{value}'. Must be one of: {valid_statuses}."
            )
        return value

    @model_validator(mode="before")
    @classmethod
    def validate_before(cls, data: Any):
        """Set default values for BIDS participant and session IDs."""
        if isinstance(data, dict):
            if Bagel.col_bids_participant_id not in data:
                data[Bagel.col_bids_participant_id] = (
                    participant_id_to_bids_participant_id(
                        data[Bagel.col_participant_id]
                    )
                )
            if Bagel.col_bids_session_id not in data:
                data[Bagel.col_bids_session_id] = session_id_to_bids_session_id(
                    data[Bagel.col_session_id]
                )

        return data

    @model_validator(mode="after")
    def validate_after(self):
        """Check fields."""
        check_participant_id(self.participant_id, raise_error=True)
        check_session_id(self.session_id, raise_error=True)
        return self


class Bagel(BaseTabular):
    """A file to track data availability/processing status."""

    # column names
    col_participant_id = "participant_id"
    col_bids_participant_id = "bids_participant_id"
    col_session_id = "session_id"
    col_bids_session_id = "bids_session_id"
    col_pipeline_name = "pipeline_name"
    col_pipeline_version = "pipeline_version"
    col_pipeline_step = "pipeline_step"
    col_status = "status"

    # pipeline statuses
    status_success = STATUS_SUCCESS
    status_fail = STATUS_FAIL
    status_incomplete = STATUS_INCOMPLETE
    status_unavailable = STATUS_UNAVAILABLE

    # for sorting/comparing between bagels
    index_cols = [
        col_participant_id,
        col_bids_participant_id,
        col_session_id,
        col_pipeline_name,
        col_pipeline_version,
        col_pipeline_step,
    ]

    _metadata = BaseTabular._metadata + [
        "col_participant_id",
        "col_bids_participant",
        "col_session_id",
        "col_bids_session",
        "col_pipeline_name",
        "col_pipeline_version",
        "col_pipeline_step",
        "col_status",
        "status_success",
        "status_fail",
        "status_incomplete",
        "status_unavailable",
        "index_cols",
    ]

    # set the model
    model = BagelModel

    def get_completed_participants_sessions(
        self,
        pipeline_name: str,
        pipeline_version: str,
        pipeline_step: str,
        participant_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """
        Get participant-session pairs that have successfully completed a pipeline run.

        Can optionally filter within a specific participant and/or session.
        """
        if participant_id is None:
            participant_ids = set(self[self.col_participant_id])
        else:
            participant_ids = {participant_id}
        if session_id is None:
            session_ids = set(self[self.col_session_id])
        else:
            session_ids = {session_id}

        bagel_subset = self.loc[
            (self[self.col_pipeline_name] == pipeline_name)
            & (self[self.col_pipeline_version] == pipeline_version)
            & (self[self.col_pipeline_step] == pipeline_step)
            & (self[self.col_participant_id].isin(participant_ids))
            & (self[self.col_session_id].isin(session_ids))
            & (self[self.col_status] == self.status_success)
        ]

        yield from bagel_subset[
            [self.col_participant_id, self.col_session_id]
        ].itertuples(index=False)
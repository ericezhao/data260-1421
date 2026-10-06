import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import { api, errorMessage } from "../api/inspectionsApi.js";

export const PAGE_SIZE = 20;

export const fetchInspections = createAsyncThunk(
  "inspections/fetch",
  async ({ skip = 0, limit = PAGE_SIZE } = {}, { rejectWithValue }) => {
    try {
      const res = await api.get("/api/inspections", { params: { skip, limit } });
      return { items: res.data, skip, hasMore: res.data.length === limit };
    } catch (err) {
      return rejectWithValue(errorMessage(err));
    }
  }
);

export const createInspection = createAsyncThunk(
  "inspections/create",
  async (payload, { rejectWithValue }) => {
    try {
      const res = await api.post("/api/inspections", payload);
      return res.data;
    } catch (err) {
      return rejectWithValue(errorMessage(err));
    }
  }
);

export const updateInspection = createAsyncThunk(
  "inspections/update",
  async ({ id, changes }, { rejectWithValue }) => {
    try {
      const res = await api.put(`/api/inspections/${id}`, changes);
      return res.data;
    } catch (err) {
      return rejectWithValue(errorMessage(err));
    }
  }
);

export const deleteInspection = createAsyncThunk(
  "inspections/delete",
  async (id, { rejectWithValue }) => {
    try {
      await api.delete(`/api/inspections/${id}`);
      return id;
    } catch (err) {
      return rejectWithValue(errorMessage(err));
    }
  }
);

const initialState = {
  items: [],
  skip: 0,
  hasMore: false,
  status: "idle", // idle | loading | succeeded | failed
  error: null,
};

const inspectionsSlice = createSlice({
  name: "inspections",
  initialState,
  reducers: {
    resetInspections: () => initialState,
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchInspections.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(fetchInspections.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.items = action.payload.items;
        state.skip = action.payload.skip;
        state.hasMore = action.payload.hasMore;
      })
      .addCase(fetchInspections.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.payload;
      })
      .addCase(createInspection.fulfilled, (state, action) => {
        state.items.unshift(action.payload);
        state.error = null;
      })
      .addCase(updateInspection.fulfilled, (state, action) => {
        const index = state.items.findIndex((item) => item.id === action.payload.id);
        if (index === -1) {
          state.items.unshift(action.payload);
        } else {
          state.items[index] = action.payload;
        }
        state.error = null;
      })
      .addCase(deleteInspection.fulfilled, (state, action) => {
        state.items = state.items.filter((item) => item.id !== action.payload);
        state.error = null;
      })
      .addCase(deleteInspection.rejected, (state, action) => {
        state.error = action.payload;
      });
  },
});

export const { resetInspections } = inspectionsSlice.actions;
export default inspectionsSlice.reducer;

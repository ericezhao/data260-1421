import { configureStore } from "@reduxjs/toolkit";
import inspectionsReducer from "./features/inspectionsSlice.js";

export const store = configureStore({
  reducer: {
    inspections: inspectionsReducer,
  },
});

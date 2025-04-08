import { Route, Routes } from "react-router-dom"

import ApiKeyForm from "./pages/ApiKeyForm"
import HomePage from "./pages/HomePage"
import '../tailwind.css'


export const Routing = () => (
  <Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="/login" element={<ApiKeyForm />} />
  </Routes>
)
import type { Metadata } from "next";
import PricingBasic from "@/components/pricing/pricing-section";

export const metadata: Metadata = {
  title: "Pricing | SurfSense",
  description: "Explore SurfSense plans and pricing options.",
};

const page = () => {
  return (
    <div>
      <PricingBasic />
    </div>
  );
};

export default page;

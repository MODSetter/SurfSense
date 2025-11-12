const uploadDocument = async (formData: FormData) => {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/fileupload`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${window.localStorage.getItem(
          "surfsense_bearer_token"
        )}`,
      },
      body: formData,
    }
  );

  if (!response.ok) {
    throw new Error("Upload failed");
  }

  await response.json();
};

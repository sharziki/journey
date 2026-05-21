export async function POST(request: Request) {
  const body = await request.json();
  return Response.json({ id: "lead_demo", email: body.email, status: "new" });
}

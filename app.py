
import uuid
from datetime import date

import streamlit as st

from database.db_setup import create_database
from database.seed_data import seed_database
from agents.workflow import warranty_workflow
from tools.customer_warranty_tool import assess_customer_warranty
from tools.ticket_tool import create_support_ticket, update_ticket_status
from analytics.ticket_analytics import load_tickets, get_ticket_metrics


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Warranty Intelligence",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Warranty & After-Sales Intelligence")

st.caption(
    "AI-assisted product support | Evidence-based warranty estimates "
    "| Multi-agent research | Internal ticket management"
)


# --------------------------------------------------
# DATABASE BOOTSTRAP (warranty.db is git-ignored)
# --------------------------------------------------

@st.cache_resource
def init_database():
    create_database()
    seed_database()
    return True


init_database()


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "case_id" not in st.session_state:
    st.session_state.case_id = str(uuid.uuid4())

if "analysis" not in st.session_state:
    st.session_state.analysis = None

if "ticket" not in st.session_state:
    st.session_state.ticket = None


# --------------------------------------------------
# APPLICATION TABS
# --------------------------------------------------

tab1, tab2, tab3 = st.tabs([
    "Customer Assistance",
    "Agent Activity",
    "Analytics Dashboard"
])


# ==================================================
# TAB 1: CUSTOMER ASSISTANCE
# ==================================================

with tab1:

    st.subheader("Describe Your Product Issue")

    with st.form("customer_form"):

        col1, col2 = st.columns(2)

        with col1:
            customer_name = st.text_input(
                "Customer Name"
            )

            brand = st.text_input(
                "Brand",
                placeholder="HP"
            )

            product = st.text_input(
                "Product and Model",
                placeholder="Pavilion laptop"
            )

        with col2:
            purchase_date = st.date_input(
                "Purchase Date",
                value=date.today(),
                max_value=date.today()
            )

            warranty_months = st.number_input(
                "Warranty Duration (Months)",
                min_value=1,
                max_value=120,
                value=12,
                step=1
            )

        issue = st.text_area(
            "Describe the Problem",
            placeholder="My laptop overheats after 20 minutes of use."
        )

        submitted = st.form_submit_button(
            "Analyse Product Issue",
            type="primary"
        )

    # --------------------------------------------------
    # PROCESS CUSTOMER SUBMISSION
    # --------------------------------------------------

    if submitted:

        if not all([
            customer_name.strip(),
            brand.strip(),
            product.strip(),
            issue.strip()
        ]):

            st.error(
                "Please complete all customer and product details."
            )

        else:

            warranty = assess_customer_warranty(
                purchase_date.isoformat(),
                int(warranty_months)
            )

            complaint = (
                f"My {brand} {product} has this problem: {issue}. "
                "Please assess the issue and find troubleshooting guidance."
            )

            with st.spinner(
                "Agents are analysing your complaint..."
            ):

                try:

                    result = warranty_workflow.invoke(
                        {
                            "customer_issue": complaint,
                            "customer_name": customer_name,
                            "brand": brand,
                            "purchase_date": purchase_date.isoformat(),
                            "warranty_months": int(warranty_months),
                            "create_ticket_requested": False,
                            "execution_trace": []
                        },
                        config={
                            "configurable": {
                                "thread_id": st.session_state.case_id
                            }
                        }
                    )

                    st.session_state.analysis = {
                        "result": result,
                        "warranty": warranty,
                        "customer": customer_name,
                        "brand": brand,
                        "product": product,
                        "issue": issue
                    }

                    st.session_state.ticket = None

                except Exception as error:

                    st.error(
                        f"Workflow error: {error}"
                    )

    # --------------------------------------------------
    # DISPLAY ANALYSIS RESULTS
    # --------------------------------------------------

    analysis = st.session_state.analysis

    if analysis:

        result = analysis["result"]

        warranty = (
            result.get("warranty_result")
            or analysis["warranty"]
        )

        st.divider()

        st.subheader("Warranty Assessment")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Estimated Status",
            warranty.get("status", "UNKNOWN")
        )

        col2.metric(
            "Estimated Expiry",
            warranty.get("estimated_expiry", "N/A")
        )

        col3.metric(
            "Days Remaining",
            warranty.get("days_remaining", "N/A")
        )

        st.info(
            "This is an estimate based on customer-provided information. "
            "Manufacturer approval and eligibility are not verified."
        )

        # --------------------------------------------------
        # RESEARCH AND TROUBLESHOOTING
        # --------------------------------------------------

        st.subheader("AI Research & Troubleshooting")

        research = result.get("research_result") or {}

        st.write(
            "Research Status:",
            research.get("status", "UNKNOWN")
        )

        recommendation = research.get("recommendation")

        if isinstance(recommendation, dict):

            confidence = recommendation.get(
                "confidence",
                "UNKNOWN"
            )

            verified_steps = recommendation.get(
                "safe_steps",
                []
            )

            if confidence == "LOW" or not verified_steps:

                st.warning(
                    "Automated assessment completed, but the issue "
                    "has NOT been confirmed as resolved. "
                    "Manufacturer guidance requires further verification."
                )

            else:

                st.info(
                    "Automated assessment completed. Review the suggested "
                    "steps before deciding whether the issue is resolved."
                )

            st.write(
                recommendation.get("summary", "")
            )

            st.markdown("**Suggested Steps**")

            for step in verified_steps:
                st.write("•", step)

            for warning in recommendation.get("warnings", []):
                st.warning(warning)

            st.write(
                "**Confidence:**",
                confidence
            )

            st.write(
                "**Next Action:**",
                recommendation.get("next_action", "")
            )

        elif recommendation:

            st.write(recommendation)

        # --------------------------------------------------
        # MANUFACTURER SOURCES
        # --------------------------------------------------

        sources = research.get("sources", [])

        if sources:

            st.markdown("**Manufacturer Research Sources**")

            for source in sources:

                source_url = source.get("url", "")
                evidence_type = source.get(
                    "evidence_type",
                    "UNKNOWN"
                )

                if source_url:
                    st.markdown(
                        f"- [{source_url}]({source_url}) "
                        f"— {evidence_type}"
                    )

        # --------------------------------------------------
        # SUPPORT TICKET
        # --------------------------------------------------

        st.divider()

        st.subheader("Support Ticket")

        st.write(
            "If the issue remains unresolved, you can create "
            "an internal support ticket."
        )

        if st.session_state.ticket:

            st.success(
                "Ticket created: "
                + st.session_state.ticket["ticket_id"]
            )

        elif st.button("Create Support Ticket"):

            ticket = create_support_ticket(
                customer_name=analysis["customer"],
                brand=analysis["brand"],
                product=analysis["product"],
                issue=analysis["issue"],
                request_id=st.session_state.case_id
            )

            if ticket["status"] == "SUCCESS":

                st.session_state.ticket = ticket
                st.rerun()

            else:

                st.error(ticket)


# ==================================================
# TAB 2: AGENT ACTIVITY
# ==================================================

with tab2:

    st.subheader("Multi-Agent Execution Trace")

    if st.session_state.analysis:

        result = st.session_state.analysis["result"]

        for index, event in enumerate(
            result.get("execution_trace", []),
            start=1
        ):

            st.write(
                f"**{index}.** {event}"
            )

        with st.expander("View Structured Agent Outputs"):

            st.json({
                "plan": result.get("plan"),
                "warranty_result": result.get("warranty_result"),
                "research_result": result.get("research_result"),
                "next_action": result.get("next_action")
            })

    else:

        st.info(
            "Analyse a customer complaint to see agent activity."
        )


# ==================================================
# TAB 3: ANALYTICS DASHBOARD
# ==================================================

with tab3:

    st.subheader("After-Sales Support Analytics")

    st.caption(
        "Operational intelligence based on actual tickets "
        "created within this application."
    )

    if st.button("Refresh Dashboard"):
        st.rerun()

    df = load_tickets()

    metrics = get_ticket_metrics(df)

    # --------------------------------------------------
    # KEY PERFORMANCE INDICATORS
    # --------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Total Tickets",
        metrics["total_tickets"]
    )

    c2.metric(
        "Open Tickets",
        metrics["open_tickets"]
    )

    c3.metric(
        "Resolved Tickets",
        metrics["resolved_tickets"]
    )

    c4.metric(
        "Resolution Rate",
        f'{metrics["resolution_rate"]}%'
    )

    # --------------------------------------------------
    # DASHBOARD VISUALISATIONS
    # --------------------------------------------------

    if df.empty:

        st.info(
            "No support tickets available yet. "
            "Create a ticket through Customer Assistance."
        )

    else:

        st.divider()

        left, right = st.columns(2)

        with left:

            st.markdown("#### Tickets by Brand")

            brand_counts = (
                df["brand"]
                .value_counts()
                .rename_axis("Brand")
                .reset_index(name="Tickets")
            )

            st.bar_chart(
                brand_counts,
                x="Brand",
                y="Tickets"
            )

        with right:

            st.markdown("#### Ticket Status Distribution")

            status_counts = (
                df["status"]
                .value_counts()
                .rename_axis("Status")
                .reset_index(name="Tickets")
            )

            st.bar_chart(
                status_counts,
                x="Status",
                y="Tickets"
            )

        # --------------------------------------------------
        # DAILY TICKET TREND
        # --------------------------------------------------

        st.markdown("#### Daily Ticket Trend")

        daily = df.dropna(
            subset=["created_at"]
        ).copy()

        if not daily.empty:

            daily["Date"] = daily["created_at"].dt.date

            daily_counts = (
                daily.groupby("Date")
                .size()
                .reset_index(name="Tickets")
            )

            st.line_chart(
                daily_counts,
                x="Date",
                y="Tickets"
            )

        # --------------------------------------------------
        # TICKET RECORDS
        # --------------------------------------------------

        st.markdown("#### Ticket Records")

        brand_options = ["All"] + sorted(
            df["brand"].unique().tolist()
        )

        selected_brand = st.selectbox(
            "Filter by Brand",
            brand_options
        )

        filtered = df.copy()

        if selected_brand != "All":

            filtered = filtered[
                filtered["brand"] == selected_brand
            ]

        st.dataframe(
            filtered,
            width="stretch",
            hide_index=True
        )

        st.caption(
            "Data source: application-managed SQLite support tickets. "
            "These are not manufacturer-issued claim records."
        )

        # --------------------------------------------------
        # MANAGE SUPPORT TICKETS
        # --------------------------------------------------

        st.divider()

        st.markdown("#### Manage Support Ticket")

        ticket_options = df["ticket_id"].tolist()

        selected_ticket = st.selectbox(
            "Select Ticket ID",
            ticket_options
        )

        new_status = st.selectbox(
            "Update Ticket Status",
            [
                "OPEN",
                "IN_PROGRESS",
                "RESOLVED"
            ]
        )

        if st.button("Save Ticket Status"):

            response = update_ticket_status(
                selected_ticket,
                new_status
            )

            if response["status"] == "SUCCESS":

                st.success(
                    "Ticket status updated successfully."
                )

                st.rerun()

            else:

                st.error(
                    response.get(
                        "message",
                        "Update failed."
                    )
                )

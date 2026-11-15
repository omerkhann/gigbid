let
    Source = Sql.Database("pharma-sql-server", "SalesDB", [Query=
        "SELECT
            s.SaleID,
            s.SaleDate,
            s.Quantity,
            s.Amount,
            p.ProductName,
            c.CustomerName,
            m.ManagerName
        FROM Sales s
        INNER JOIN Products p ON s.ProductID = p.ProductID
        INNER JOIN Customers c ON s.CustomerID = c.CustomerID
        INNER JOIN Managers m ON s.ManagerID = m.ManagerID
        WHERE s.SaleDate >= DATEADD(MONTH, -12, GETDATE())"
    ]),
    #"Added Custom Date" = Table.AddColumn(Source, "YearMonth", each Date.ToText([SaleDate], "yyyy-MM"), type text),
    #"Grouped by YearMonth" = Table.Group(#"Added Custom Date", {"YearMonth"}, {
        {"TotalSales", each List.Sum([Amount]), type number},
        {"TotalQuantity", each List.Sum([Quantity]), type number},
        {"UniqueCustomers", each List.Count(List.Distinct([CustomerName])), type number}
    }),
    #"Sorted by YearMonth" = Table.Sort(#"Grouped by YearMonth", {{"YearMonth", Order.Ascending}})
in
    #"Sorted by YearMonth
